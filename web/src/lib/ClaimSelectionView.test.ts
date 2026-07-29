import { fireEvent, render, screen } from "@testing-library/svelte";

import ClaimSelectionView from "./ClaimSelectionView.svelte";
import type { FactCheckJob } from "./types";

const job: FactCheckJob = {
  id: "fact-check-1",
  analysis_id: "analysis-1",
  status: "awaiting_selection",
  stage: "Choose claims to check",
  progress: 100,
  selected_candidate_ids: [],
  result: null,
  error: null,
  candidates: [
    {
      id: "claim-1",
      source_quote: "The agency reported 20 cases.",
      segment_ids: ["p1s1"],
      standalone_claim: "The agency reported 20 cases.",
      claim_type: "attributed",
      entities: ["The agency"],
      dates: [],
      numbers: ["20"],
      reason: "A specific attributed figure."
    },
    {
      id: "claim-opinion",
      source_quote: "This was a remarkable result.",
      segment_ids: ["p2s1"],
      standalone_claim: "The result was remarkable.",
      claim_type: "unsuitable",
      entities: [],
      dates: [],
      numbers: [],
      reason: "Remarkable is a subjective judgment."
    }
  ]
};

describe("ClaimSelectionView", () => {
  it("starts empty and keeps unsuitable claims out of selection", () => {
    render(ClaimSelectionView, {
      job,
      onSelect: vi.fn(),
      onReset: vi.fn()
    });

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).not.toBeChecked();
    expect(radios[1]).toBeDisabled();
    expect(screen.getByRole("button", { name: "Choose a claim" })).toBeDisabled();
    expect(screen.getByText("Nothing selected")).toBeInTheDocument();
  });

  it("saves only the claims explicitly selected by the reader", async () => {
    const onSelect = vi.fn().mockResolvedValue(undefined);
    render(ClaimSelectionView, { job, onSelect, onReset: vi.fn() });

    await fireEvent.click(screen.getAllByRole("radio")[0]);
    await fireEvent.click(screen.getByRole("button", { name: "Trace this claim" }));

    expect(onSelect).toHaveBeenCalledWith(["claim-1"]);
    expect(await screen.findByRole("status")).toHaveTextContent("Selection saved.");
  });
});
