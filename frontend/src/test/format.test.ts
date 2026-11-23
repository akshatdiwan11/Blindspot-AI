import { describe, expect, it } from "vitest";
import { conditionText } from "../components/domain";
import { int, pct, pp, pval } from "../utils/format";

describe("number formatting", () => {
  it("formats rates and differences", () => {
    expect(pct(0.1744)).toBe("17.4%");
    expect(pct(null)).toBe("—");
    expect(pct(Number.NaN)).toBe("—");
    expect(pp(0.337)).toBe("+33.7 pp");
    expect(pp(-0.05)).toBe("-5.0 pp");
    expect(int(undefined)).toBe("—");
  });
  it("never prints a p-value of zero", () => {
    expect(pval(1e-30)).toBe("< 0.0001");
    expect(pval(0.0433)).toBe("0.0433");
  });
});

describe("failure rule text", () => {
  it("renders every condition type", () => {
    expect(conditionText({ feature: "language", op: "==", value: "Hindi" })).toBe("language = Hindi");
    expect(conditionText({ feature: "input_script", op: "!=", value: "latin" })).toBe("input_script ≠ latin");
    expect(conditionText({ feature: "source", op: "is_missing" })).toBe("source is missing");
    expect(conditionText({ feature: "date_mentions", op: "between", low: 3, high: null })).toBe("date_mentions ≥ 3");
    expect(conditionText({ feature: "pages", op: "between", low: null, high: 2 })).toBe("pages < 2");
  });
});
