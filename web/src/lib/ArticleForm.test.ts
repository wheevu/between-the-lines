import { fireEvent, render, screen } from "@testing-library/svelte";

import ArticleForm from "./ArticleForm.svelte";

describe("ArticleForm", () => {
  it("starts with the quick URL flow and asks for a URL", async () => {
    render(ArticleForm);

    expect(screen.getByRole("button", { name: "Paste text" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByRole("button", { name: "Use a URL" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    await fireEvent.click(screen.getByRole("button", { name: "Translate to Vietnamese" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Add an article URL first.");
    expect(screen.getByLabelText("Article URL")).toHaveAttribute("aria-invalid", "true");
  });

  it("emits normalized form values", async () => {
    const events: unknown[] = [];
    render(ArticleForm, {
      draft: {
        mode: "text",
        sourceLanguage: "en",
        targetLanguage: "vi",
        text: "",
        url: ""
      },
      onAnalyze: (input) => events.push(input)
    });

    await fireEvent.input(screen.getByLabelText("Article text"), {
      target: { value: "  A short article.  " }
    });
    await fireEvent.change(screen.getByLabelText("Article language"), {
      target: { value: "vi" }
    });
    await fireEvent.change(screen.getByLabelText("Read in"), {
      target: { value: "ko" }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Translate to Korean" }));

    expect(events).toEqual([
      {
        mode: "text",
        sourceLanguage: "vi",
        targetLanguage: "ko",
        value: "A short article."
      }
    ]);
  });

  it("blocks text over the article limit before analysis", async () => {
    const events: unknown[] = [];
    render(ArticleForm, {
      draft: {
        mode: "text",
        sourceLanguage: "en",
        targetLanguage: "vi",
        text: "",
        url: ""
      },
      onAnalyze: (input) => events.push(input)
    });

    await fireEvent.input(screen.getByLabelText("Article text"), {
      target: { value: Array.from({ length: 2_501 }, () => "word").join(" ") }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Translate to Vietnamese" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Keep the article under 2,500 words.");
    expect(events).toEqual([]);
  });

  it("keeps the URL available when switching to the paste fallback", async () => {
    const drafts: unknown[] = [];
    render(ArticleForm, {
      draft: {
        mode: "url",
        sourceLanguage: "vi",
        targetLanguage: "en",
        text: "",
        url: "https://example.com/article"
      },
      errorMessage: "Couldn't find enough article text. Paste the text instead.",
      onDraftChange: (draft) => drafts.push(draft)
    });

    await fireEvent.click(screen.getByRole("button", { name: "Paste the text instead" }));

    expect(screen.getByLabelText("Article text")).toBeInTheDocument();
    expect(drafts.at(-1)).toEqual({
      mode: "text",
      sourceLanguage: "vi",
      targetLanguage: "en",
      text: "",
      url: "https://example.com/article"
    });
  });
});
