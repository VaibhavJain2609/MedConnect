variable "name" {
  description = "Web ACL name, e.g. medconnect-staging"
  type        = string
}

variable "environment" {
  type = string
}

# WAFv2 rate-based rules count over a trailing 5-minute window — there is no
# sub-5-minute granularity the way Nginx's per-second limit_req_zone had.
# These defaults approximate Nginx's rates scaled to that window:
# 10 req/s general -> ~3000/5min; 10 req/min on auth -> ~50/5min, rounded up
# with headroom for legitimate retry/refresh bursts.
variable "api_rate_limit_per_5min" {
  type    = number
  default = 3000
}

variable "auth_rate_limit_per_5min" {
  type    = number
  default = 100
}

variable "tags" {
  type    = map(string)
  default = {}
}
