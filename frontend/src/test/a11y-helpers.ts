import { axe } from "vitest-axe";
import type AxeCore from "axe-core";
import { expect } from "vitest";

export async function checkA11y(
  container: HTMLElement,
  options?: AxeCore.RunOptions,
): Promise<void> {
  const results = await axe(container, options);
  const violations = results.violations;
  if (violations.length > 0) {
    const messages = violations.map(
      v => `[${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} node(s))`,
    );
    expect(violations, `Accessibility violations:\n${messages.join("\n")}`).toHaveLength(0);
  }
}
