/**
 * Tests for RecordVersionHistory — the patient-facing amendment-chain view.
 *
 * The axios instance in `@/lib/api` is replaced by apiMock (the repo-wide
 * pattern); `@/lib/api/records` stays real and funnels through it.
 */

import {
  render,
  screen,
  waitFor,
} from "../../../../tests/utils/test-utils";
import type { RecordVersion } from "@/lib/api/records";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  // Lazy require: `@/lib/api` may be pulled in via test-utils before this
  // factory runs — a direct binding would hit the TDZ.
  default: require("../../../../tests/mocks/api-mock").apiMock,
}));

import { apiMock, resetApiMock } from "../../../../tests/mocks/api-mock";
import {
  RecordVersionHistory,
  diffRecordVersions,
} from "../record-version-history";

function makeVersion(overrides: Partial<RecordVersion> = {}): RecordVersion {
  return {
    id: "v-1",
    version: 1,
    is_latest: false,
    record_type: "opd_note",
    title: "Visit",
    description: "initial note",
    fhir_bundle: null,
    document_url: null,
    source: "doctor",
    amended_from_id: null,
    doctor_id: "doc-1",
    doctor_name: "Dr. Test",
    created_at: "2025-01-01T10:00:00Z",
    updated_at: "2025-01-01T10:00:00Z",
    ...overrides,
  };
}

describe("diffRecordVersions", () => {
  it("reports changed scalar fields", () => {
    const original = makeVersion();
    const amended = makeVersion({
      version: 2,
      title: "Visit (corrected)",
      description: "amended note",
    });
    const changes = diffRecordVersions(original, amended);
    const labels = changes.map((c) => c.label);
    expect(labels).toEqual(["Title", "Description"]);
    expect(changes[0]).toMatchObject({ before: "Visit", after: "Visit (corrected)" });
  });

  it("diffs fhir_bundle leaves and ignores volatile timestamp fields", () => {
    const original = makeVersion({
      fhir_bundle: {
        timestamp: "2025-01-01T10:00:00Z",
        meta: { lastUpdated: "2025-01-01T10:00:00Z" },
        entry: [
          {
            resource: {
              date: "2025-01-01T10:00:00Z",
              text: { div: "mild fever" },
            },
          },
        ],
      },
    });
    const amended = makeVersion({
      version: 2,
      fhir_bundle: {
        timestamp: "2025-01-02T10:00:00Z",
        meta: { lastUpdated: "2025-01-02T10:00:00Z" },
        entry: [
          {
            resource: {
              date: "2025-01-02T10:00:00Z",
              text: { div: "high fever" },
            },
          },
        ],
      },
    });
    const changes = diffRecordVersions(original, amended);
    expect(changes).toHaveLength(1);
    expect(changes[0].label).toContain("text.div");
    expect(changes[0].before).toBe("mild fever");
    expect(changes[0].after).toBe("high fever");
  });

  it("returns empty when nothing clinical changed", () => {
    const original = makeVersion();
    const amended = makeVersion({ version: 2 });
    expect(diffRecordVersions(original, amended)).toHaveLength(0);
  });
});

describe("RecordVersionHistory", () => {
  beforeEach(() => resetApiMock());

  it("renders nothing when the record has no amendments", async () => {
    apiMock.get.mockResolvedValueOnce({
      data: { data: [makeVersion({ is_latest: true })], total: 1 },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {},
    });
    const { container } = render(<RecordVersionHistory recordId="r-1" />);
    await waitFor(() => expect(apiMock.get).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("lists versions newest-first with the amendment diff", async () => {
    apiMock.get.mockResolvedValueOnce({
      data: {
        data: [
          makeVersion(),
          makeVersion({
            id: "v-2",
            version: 2,
            is_latest: true,
            title: "Visit (corrected)",
            amended_from_id: "v-1",
            source: "amended",
            created_at: "2025-01-02T10:00:00Z",
          }),
        ],
        total: 2,
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {},
    });
    render(<RecordVersionHistory recordId="r-1" />);

    expect(await screen.findByText("Version history")).toBeInTheDocument();
    expect(screen.getByText("Version 2")).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Latest")).toBeInTheDocument();
    expect(screen.getByText("Original")).toBeInTheDocument();
    // diff row: title changed
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Visit (corrected)")).toBeInTheDocument();
    expect(apiMock.get).toHaveBeenCalledWith(
      "/api/v1/patients/records/r-1/versions"
    );
  });
});
