import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SortMenu } from "./SortMenu";

describe("SortMenu", () => {
  it("labels the button with the order currently applied", () => {
    const html = renderToStaticMarkup(
      <SortMenu value={{ key: "created", dir: "desc" }} onChange={() => {}} />,
    );
    expect(html).toContain("Sort by: Newest first");
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
  });

  it("keeps the menu closed until the button is pressed", () => {
    const html = renderToStaticMarkup(
      <SortMenu value={{ key: "title", dir: "asc" }} onChange={() => {}} />,
    );
    expect(html).toContain("Sort by: Title A–Z");
    expect(html).not.toContain("menuitemradio");
    expect(html).not.toContain("Sort cases by");
  });
});
