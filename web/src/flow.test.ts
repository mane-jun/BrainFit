import { describe, expect, it } from "vitest";
import { allSensorsGood, restSeconds, responseLabel } from "./flow";

describe("실시간 진행 규칙", () => {
  it("네 센서가 모두 70% 이상일 때만 착용 확인을 허용한다", () => {
    expect(allSensorsGood({ TP9: 0.9, AF7: 0.72, AF8: 0.8, TP10: 1 })).toBe(
      true,
    );
    expect(allSensorsGood({ TP9: 0.9, AF7: 0.69, AF8: 0.8, TP10: 1 })).toBe(
      false,
    );
  });

  it("시연·정식 기준선은 각각 30초·60초다", () => {
    expect(restSeconds("demo")).toBe(30);
    expect(restSeconds("standard")).toBe(60);
  });

  it("판단 보류를 약한 반응으로 표시하지 않는다", () => {
    expect(responseLabel(null)).toBe("판단 보류");
    expect(responseLabel(false)).toBe("반응 약함");
  });
});
