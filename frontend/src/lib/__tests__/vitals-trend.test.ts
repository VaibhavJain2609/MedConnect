import {
  computeTrendSummary,
  groupVitalsByType,
  STABLE_MIN_EPSILON,
} from "@/lib/vitals-trend";
import type { Vital, VitalType } from "@/lib/api/vitals";

let seq = 0;
function reading(
  value: number,
  recordedAt: string,
  vitalType: VitalType = "bp_systolic",
  abnormal = false
): Vital {
  seq += 1;
  return {
    id: `v-${seq}`,
    patient_id: "p-1",
    vital_type: vitalType,
    value,
    unit: "mmHg",
    recorded_at: recordedAt,
    created_at: recordedAt,
    abnormal_flag: abnormal,
  };
}

describe("computeTrendSummary", () => {
  it("returns null for fewer than 2 readings", () => {
    expect(computeTrendSummary([])).toBeNull();
    expect(
      computeTrendSummary([reading(120, "2024-01-01T10:00:00Z")])
    ).toBeNull();
  });

  it("reports a rising trend when the delta exceeds the stable band", () => {
    // 118 → 132 is a ~12% rise on a 118 baseline (> 5%)
    const s = computeTrendSummary([
      reading(118, "2024-01-01T10:00:00Z"),
      reading(125, "2024-01-10T10:00:00Z"),
      reading(132, "2024-01-30T10:00:00Z"),
    ]);
    expect(s).not.toBeNull();
    expect(s!.direction).toBe("rising");
    expect(s!.first).toBe(118);
    expect(s!.last).toBe(132);
    expect(s!.delta).toBe(14);
    expect(s!.count).toBe(3);
  });

  it("reports a falling trend", () => {
    // 100 → 80 is a 20% drop
    const s = computeTrendSummary([
      reading(100, "2024-01-01T10:00:00Z"),
      reading(80, "2024-01-30T10:00:00Z"),
    ]);
    expect(s!.direction).toBe("falling");
    expect(s!.delta).toBe(-20);
  });

  it("reports stable for changes inside the 5% band", () => {
    // 120 → 124 is ~3.3% — below STABLE_THRESHOLD_RATIO
    const s = computeTrendSummary([
      reading(120, "2024-01-01T10:00:00Z"),
      reading(124, "2024-01-30T10:00:00Z"),
    ]);
    expect(s!.direction).toBe("stable");
  });

  it("uses the absolute epsilon floor when the baseline is near zero", () => {
    // first = 0 → epsilon = STABLE_MIN_EPSILON; delta 0.4 is stable, 0.6 rising
    const stable = computeTrendSummary([
      reading(0, "2024-01-01T00:00:00Z", "weight_kg"),
      reading(STABLE_MIN_EPSILON - 0.1, "2024-01-02T00:00:00Z", "weight_kg"),
    ]);
    expect(stable!.direction).toBe("stable");

    const rising = computeTrendSummary([
      reading(0, "2024-01-01T00:00:00Z", "weight_kg"),
      reading(STABLE_MIN_EPSILON + 0.1, "2024-01-02T00:00:00Z", "weight_kg"),
    ]);
    expect(rising!.direction).toBe("rising");
  });

  it("sorts out-of-order readings chronologically", () => {
    const s = computeTrendSummary([
      reading(140, "2024-01-30T10:00:00Z"),
      reading(110, "2024-01-01T10:00:00Z"),
      reading(125, "2024-01-15T10:00:00Z"),
    ]);
    expect(s!.first).toBe(110);
    expect(s!.last).toBe(140);
    expect(s!.firstRecordedAt).toBe("2024-01-01T10:00:00Z");
    expect(s!.lastRecordedAt).toBe("2024-01-30T10:00:00Z");
    expect(s!.direction).toBe("rising");
  });

  it("counts abnormal-flagged readings", () => {
    const s = computeTrendSummary([
      reading(118, "2024-01-01T10:00:00Z"),
      reading(190, "2024-01-15T10:00:00Z", "bp_systolic", true),
      reading(200, "2024-01-30T10:00:00Z", "bp_systolic", true),
    ]);
    expect(s!.abnormalCount).toBe(2);
    expect(s!.direction).toBe("rising");
  });

  it("does not mutate the input array", () => {
    const input = [
      reading(130, "2024-01-10T10:00:00Z"),
      reading(110, "2024-01-01T10:00:00Z"),
    ];
    computeTrendSummary(input);
    expect(input[0].value).toBe(130);
    expect(input[1].value).toBe(110);
  });
});

describe("groupVitalsByType", () => {
  it("groups mixed vitals by type, chronologically sorted", () => {
    const groups = groupVitalsByType([
      reading(130, "2024-01-10T10:00:00Z", "bp_systolic"),
      reading(98, "2024-01-05T10:00:00Z", "spo2"),
      reading(110, "2024-01-01T10:00:00Z", "bp_systolic"),
      reading(96, "2024-01-01T10:00:00Z", "spo2"),
    ]);
    expect(Object.keys(groups).sort()).toEqual(["bp_systolic", "spo2"]);
    expect(groups.bp_systolic!.map((v) => v.value)).toEqual([110, 130]);
    expect(groups.spo2!.map((v) => v.value)).toEqual([96, 98]);
  });

  it("returns an empty object for no vitals", () => {
    expect(groupVitalsByType([])).toEqual({});
  });
});
