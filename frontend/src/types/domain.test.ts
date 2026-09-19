import { describe, expect, it } from "vitest";

import type { DocumentBlock } from "./domain";

describe("domain contract", () => {
  it("represents a protected unknown paragraph", () => {
    const block: DocumentBlock = {
      schema_version: "1.0",
      id: "p-0001",
      order: 0,
      kind: "paragraph",
      text: "合成测试内容",
      role: "unknown",
      confidence: 0,
      decision_source: "unknown",
      requires_confirmation: true,
      style: {},
      source_anchor: { part_name: "word/document.xml", paragraph_index: 0 },
      protected: true,
      metadata: {},
    };

    expect(block.protected).toBe(true);
    expect(block.role).toBe("unknown");
  });
});
