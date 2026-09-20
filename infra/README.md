# MedConnect infrastructure

Terraform (`infra/terraform`) provisions AWS; Kustomize (`infra/k8s`) deploys
the app onto the EKS cluster Terraform creates; GitHub Actions
(`.github/workflows`) wires CI, image build/scan/sign, and CD together.

**Nothing here has been applied.** No AWS resource has been created, no
GitHub secret has been set, and this pipeline has never run against a real
account. Everything below is what *you* need to do, in order, before the
first real deploy — this document does not describe a completed setup.

## 1. Bootstrap the Terraform state backend (once, by hand)

Every environment's `backend.tf` points at one shared S3 bucket + DynamoDB
lock table. Terraform can't create its own backend, so create these once
with the AWS CLI before the first `terraform init` anywhere in this repo:

```bash
aws s3api create-bucket --bucket medconnect-terraform-state \
  --region ap-south-1 --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket medconnect-terraform-state \
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name medconnect-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region ap-south-1
```

If you use a different bucket/table name or region, update the `bucket` /
`dynamodb_table` / `region` values in all three `environments/*/backend.tf`
files to match — they currently hardcode `medconnect-terraform-state` /
`medconnect-terraform-locks` / `ap-south-1`.

## 2. Apply order

`environments/staging` and `environments/prod` both read
`environments/shared`'s state via `terraform_remote_state` (VPC id, subnet
ids, cluster security group, GitHub Actions role ARN, etc.) — `shared` must
exist first.

```bash
cd infra/terraform/environments/shared
cp terraform.tfvars.example terraform.tfvars   # fill in github_org at minimum
terraform init
terraform plan
terraform apply

cd ../staging
cp terraform.tfvars.example terraform.tfvars   # needs a real domain + ACM cert
terraform init
terraform plan
terraform apply

cd ../prod
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

`staging` and `prod` are independent of each other (only `shared` is a
shared dependency), so they can be applied in either order, or in parallel
once `shared` exists.

### The domain and ACM certificate are on you

`auth_hostname`, `app_hostname`, and `acm_certificate_arn` in each
environment's `terraform.tfvars` need a real domain you own, with DNS
pointed at the ALB (created by the AWS Load Balancer Controller once the
Ingress is applied — its address isn't known until after the K8s apply
step, so DNS has to be a follow-up, not part of `terraform apply`) and an
ACM certificate covering both hostnames (or a wildcard) validated in the
same region. This repo does not provision Route53 or ACM — that's
intentionally out of scope, since it requires a domain this pipeline has no
way to know about.

## 3. Deploy the Kubernetes manifests (first time, by hand)

The CD pipeline (`cd.yml`) handles this on every push to `master` once
GitHub Actions is wired up (step 5 below), but the very first deploy — or
any time you want to bypass CI — can be done manually:

```bash
aws eks update-kubeconfig --name medconnect --region ap-south-1

# Patch in real image references (see step 2's ECR repo URLs from
# `terraform output ecr_repository_urls` in environments/shared):
cd infra/k8s/overlays/staging
kustomize edit set image \
  medconnect-backend=<ecr-url>/medconnect-backend:<tag> \
  medconnect-frontend=<ecr-url>/medconnect-frontend:<tag> \
  medconnect-keycloak=<ecr-url>/medconnect-keycloak:<tag>

kubectl apply -k infra/k8s/overlays/staging
```

Before this will actually work end to end, also patch the two
`PLACEHOLDER_*` values each overlay's `kustomization.yaml` still carries —
`terraform output waf_web_acl_arn` (from `environments/staging` or `prod`)
for the WAF ARN, and your real ACM certificate ARN — since Terraform's WAF
and the Ingress are wired together by hand, not automatically.

## 4. Verifying without touching AWS

Everything below was actually run against this repo's real files —
not a description of what *should* pass, but what already does:

```bash
# Terraform — real syntax/type checking, no AWS credentials needed
terraform fmt -check -recursive infra/terraform
cd infra/terraform/environments/<shared|staging|prod>
terraform init -backend=false && terraform validate

# Kubernetes — real rendering + schema validation, no cluster needed
kubectl kustomize infra/k8s/overlays/staging
kubectl kustomize infra/k8s/overlays/prod
kubeconform -strict -ignore-missing-schemas -kubernetes-version 1.31.0 -summary <(kubectl kustomize infra/k8s/overlays/staging)
```

`kubectl apply --dry-run=client` was tried too, but even in client-dry-run
mode `kubectl` queries a live API server's discovery endpoint to resolve
each kind's RESTMapping — verified locally, it fails outright with no
cluster reachable, dummy kubeconfig or not. `kubeconform` doesn't need a
cluster at all, which is why CI (`ci.yml`'s `kustomize` job) uses that
instead.

None of this proves the pipeline works against real EKS/RDS/ElastiCache —
that has never been exercised. The first real `terraform apply` and first
real CD run are both genuinely untested paths.

## 5. GitHub repository configuration

**Secrets** (Settings → Secrets and variables → Actions → Secrets):

| Name | Value |
|---|---|
| `AWS_ROLE_ARN` | `terraform output github_actions_role_arn` from `environments/shared` |

**Variables** (same page, Variables tab):

| Name | Value |
|---|---|
| `AWS_REGION` | `ap-south-1` (or whatever you set in `terraform.tfvars`) |
| `EKS_CLUSTER_NAME` | `medconnect` |
| `DEPLOY_WEBHOOK_URL` | Optional — a Slack/Discord/generic incoming-webhook URL; `cd.yml`'s `notify` job posts to it only if this variable is set |

**Environments** (Settings → Environments) — create both `staging` and
`production`. `deploy.yml`'s `environment: ${{ inputs.environment }}` and
`rollback.yml`'s `environment:` line both gate on these; add required
reviewers to `production` if you want the human-approval gate the original
plan called for — an empty Environment with no protection rules is a no-op.

## 6. Rough monthly cost estimate (ap-south-1, on-demand, per environment)

This is a rough order-of-magnitude estimate for **staging-sized**
infrastructure, not a quote — actual AWS pricing varies by exact instance
availability and changes over time.

| Resource | Staging default | ~Monthly |
|---|---|---|
| EKS control plane | shared across both environments | ~$73 |
| EC2 (2× t3.large, on-demand) | shared node group | ~$120 |
| RDS (db.t4g.medium, single-AZ, 50GB gp3) | staging | ~$60 |
| ElastiCache (cache.t4g.small, no replica) | staging | ~$25 |
| ALB | one per environment sharing the cluster's LBC | ~$20 + data |
| NAT Gateway | one, shared | ~$35 + data |
| **Staging total (excl. shared cluster)** | | **~$140/mo** |
| **Shared cluster (control plane + nodes)** | | **~$193/mo** |

Prod's defaults (`db.r6g.large` multi-AZ, `cache.r6g.large` with replica,
2 nodes minimum via HPA) roughly double the data-store lines. Data
transfer, CloudWatch Logs retention, and WAF request charges are not
included and are usage-dependent. **Nothing is provisioned and no cost is
incurred until you run `terraform apply` yourself.**
