import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StartProgress } from "./StartProgress";

// Server render exercises the markup states without running the rAF loop,
// which is enough to lock down what the user sees in each phase of a launch.
const render = (ui: ReactElement) => renderToStaticMarkup(ui);

/** The overlay heading — asserted exactly so step labels don't collide. */
const titleOf = (html: string) =>
  html.match(/<div class="tg-launch-title">([^<]*)<\/div>/)?.[1];

describe("StartProgress", () => {
  it("renders nothing while closed", () => {
    expect(render(<StartProgress open={false} />)).toBe("");
  });

  it("shows staged progress while the request is in flight", () => {
    const html = render(<StartProgress open />);
    expect(titleOf(html)).toBe("Starting investigation");
    expect(html).toContain("Validating case evidence");
    expect(html).toContain("Dispatching the pipeline");
    expect(html).toContain("Working…");
    // Never claims success before the API answers.
    expect(html).not.toContain('data-state="failed"');
    expect(html).not.toContain("Investigation could not start");
  });

  it("announces the created run once the API responds", () => {
    const html = render(<StartProgress open ready />);
    expect(titleOf(html)).toBe("Run created");
    expect(html).toContain("Opening the live run view…");
    expect(html).not.toContain("Investigation could not start");
  });

  it("surfaces the API error with a way back", () => {
    const html = render(<StartProgress open error="403 — forbidden" />);
    expect(titleOf(html)).toBe("Investigation could not start");
    expect(html).toContain("403 — forbidden");
    expect(html).toContain("Back");
    expect(html).toContain('data-state="failed"');
  });

  it("uses a custom title and ready detail", () => {
    const html = render(
      <StartProgress open ready title="Starting investigation" readyDetail="Run is live." />,
    );
    expect(html).toContain("Run is live.");
  });
});
