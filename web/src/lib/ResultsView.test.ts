import { fireEvent, render, screen } from "@testing-library/svelte";

import ResultsView from "./ResultsView.svelte";
import type { AnalysisJob, AnalysisResult } from "./types";

const result: AnalysisResult = {
  source_language: "vi",
  source_title: "Bài thử",
  source_url: null,
  segments: [
    {
      id: "p1s1",
      paragraph_index: 0,
      sentence_index: 0,
      source_text: "Câu thứ nhất.",
      translations: [
        {
          language: "en",
          text: "First sentence.",
          shadow_text: null,
          similarity: 0.95,
          back_translation_similarity: null,
          flags: []
        },
        {
          language: "ko",
          text: "첫 번째 문장.",
          shadow_text: null,
          similarity: 0.94,
          back_translation_similarity: null,
          flags: []
        }
      ]
    },
    {
      id: "p1s2",
      paragraph_index: 0,
      sentence_index: 1,
      source_text: "Câu thứ hai.",
      translations: [
        {
          language: "en",
          text: "Second sentence.",
          shadow_text: null,
          similarity: 0.96,
          back_translation_similarity: null,
          flags: []
        },
        {
          language: "ko",
          text: "두 번째 문장.",
          shadow_text: null,
          similarity: 0.93,
          back_translation_similarity: null,
          flags: []
        }
      ]
    },
    {
      id: "p2s1",
      paragraph_index: 1,
      sentence_index: 0,
      source_text: "Đoạn mới.",
      translations: [
        {
          language: "en",
          text: "New paragraph.",
          shadow_text: null,
          similarity: 0.97,
          back_translation_similarity: null,
          flags: []
        },
        {
          language: "ko",
          text: "새 문단.",
          shadow_text: null,
          similarity: 0.92,
          back_translation_similarity: null,
          flags: []
        }
      ]
    }
  ]
};

const job: AnalysisJob & { result: AnalysisResult } = {
  id: "analysis-1",
  status: "complete",
  stage: "Ready to review",
  progress: 100,
  result,
  error: null
};

describe("ResultsView", () => {
  it("shows one target at a time and reveals the original on request", async () => {
    render(ResultsView, { job });

    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "Korean" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByText("First sentence.")).toBeInTheDocument();
    expect(screen.queryByText("첫 번째 문장.")).not.toBeInTheDocument();
    expect(screen.getByText("No specific changes were flagged.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Korean" }));
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByRole("button", { name: "Korean" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByText("첫 번째 문장.")).toBeInTheDocument();
    expect(screen.queryByText("First sentence.")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("checkbox", { name: "Show original" }));
    expect(screen.getByText(/Câu thứ nhất\./)).toBeInTheDocument();
  });

  it("copies the active translation with paragraph breaks", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });
    render(ResultsView, { job });

    await fireEvent.click(screen.getByRole("button", { name: "Copy translation" }));

    expect(writeText).toHaveBeenCalledWith(
      "First sentence. Second sentence.\n\nNew paragraph."
    );
    expect(screen.getByRole("status")).toHaveTextContent("Copied.");
  });

  it("keeps Claim Trace behind the reviewer release gate", () => {
    const { unmount } = render(ResultsView, { job });

    expect(screen.queryByRole("button", { name: "Choose a claim to trace" })).not.toBeInTheDocument();
    unmount();

    render(ResultsView, { job, showClaimTrace: true });
    expect(screen.getByRole("button", { name: "Choose a claim to trace" })).toBeInTheDocument();
  });

  it("keeps long finding lists manageable until the reader asks for all", async () => {
    const noisyJob = JSON.parse(JSON.stringify(job)) as AnalysisJob & {
      result: AnalysisResult;
    };
    const english = noisyJob.result.segments[0].translations.find(
      (translation) => translation.language === "en"
    );
    if (!english) throw new Error("English fixture is missing.");
    english.flags = Array.from({ length: 5 }, (_, index) => ({
      id: `flag-${index + 1}`,
      target_language: "en",
      kind: "meaning-risk",
      category: "number",
      confidence: "high",
      source_quote: `${index + 1}`,
      translation_quote: `${index + 1}`,
      explanation: `Finding ${index + 1}`,
      alternative: null,
      signals: ["Test"]
    }));

    render(ResultsView, { job: noisyJob });

    expect(screen.getByText("Finding 4")).toBeInTheDocument();
    expect(screen.queryByText("Finding 5")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Show all 5 findings" }));

    expect(screen.getByText("Finding 5")).toBeInTheDocument();
  });
});
