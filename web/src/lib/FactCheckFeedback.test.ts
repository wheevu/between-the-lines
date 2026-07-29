import { fireEvent, render, screen } from "@testing-library/svelte";

import FactCheckFeedback from "./FactCheckFeedback.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("FactCheckFeedback", () => {
  it("records a judgment against the exact evidence target", async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init) requests.push(init);
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" }
        });
      })
    );
    render(FactCheckFeedback, {
      factCheckId: "fact-check-1",
      targetType: "evidence",
      targetId: "evidence-1",
      question: "Is this evidence relevant?"
    });

    await fireEvent.click(screen.getByRole("button", { name: "No" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Feedback saved.");
    expect(JSON.parse(String(requests[0].body))).toEqual({
      target_type: "evidence",
      target_id: "evidence-1",
      verdict: "incorrect"
    });
    expect(screen.getByLabelText("What should change? Optional")).toBeInTheDocument();
    expect(screen.getByLabelText("Better source Optional URL")).toBeInTheDocument();
  });
});
