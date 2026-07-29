import { render, screen } from "@testing-library/svelte";

import FactCheckResults from "./FactCheckResults.svelte";
import type { FactCheckJob } from "./types";

const job: FactCheckJob = {
  id: "fact-check-1",
  analysis_id: "analysis-1",
  status: "complete",
  stage: "Evidence ready to inspect",
  progress: 100,
  candidates: [],
  selected_candidate_ids: ["claim-1"],
  error: null,
  result: {
    checked_at: "2026-07-24T10:00:00Z",
    claims: [
      {
        claim: {
          id: "claim-1",
          source_quote: "The agency reported 24 buses.",
          segment_ids: ["p1s1"],
          standalone_claim: "The agency reported 24 buses.",
          claim_type: "attributed",
          entities: ["The agency"],
          dates: [],
          numbers: ["24"],
          reason: "A checkable figure."
        },
        queries: [
          {
            language: "en",
            exact_query: "\"24 buses\" agency",
            context_query: "agency bus report"
          },
          {
            language: "vi",
            exact_query: "\"24 xe buýt\" cơ quan",
            context_query: "báo cáo xe buýt cơ quan"
          },
          {
            language: "ko",
            exact_query: "\"버스 24대\" 기관",
            context_query: "기관 버스 보고서"
          }
        ],
        assessment: {
          claim_id: "claim-1",
          status: "supported",
          explanation: "Two independent reports describe the same attributed figure. [evidence-1]",
          support_evidence_ids: ["evidence-1"],
          challenge_evidence_ids: [],
          context_evidence_ids: [],
          limitations: ["This supports the attribution, not the underlying allegation."]
        },
        trace: {
          evidence_state: "corroborated",
          article_count: 1,
          independent_lineages: 1,
          languages: ["ko"],
          meaning_deltas: [
            {
              type: "attribution",
              description: "The Korean report names the agency directly."
            }
          ]
        },
        evidence: [
          {
            id: "evidence-1",
            url: "https://check.example/report",
            title: "Agency figure reviewed",
            publisher: "Example Check",
            publisher_key: "check.example",
            language: "ko",
            excerpt: "검토 결과 기관이 버스 24대를 발표한 것으로 확인됐다.",
            source_type: "professional-fact-check",
            rating: "발표 확인",
            published_at: null,
            retrieved_at: "2026-07-24T09:55:00Z",
            content_hash: "hash",
            cluster_id: "cluster",
            relevance: 0.94,
            stance: "supports",
            stance_reason: "The source confirms that the agency made the statement.",
            direct: false,
            mismatch: null,
            aligned_quote: "기관이 버스 24대를 발표한",
            alignment_state: "aligned",
            meaning_deltas: [],
            credited_origin: "The agency"
          }
        ],
        retrieval_failures: [
          {
            url: "https://blocked.example/report",
            reason: "The page could not be read safely."
          }
        ],
        error: null
      }
    ]
  }
};

describe("FactCheckResults", () => {
  it("keeps the assessment bounded to found sources and preserves provenance", () => {
    render(FactCheckResults, { job });

    expect(screen.getByText("Corroborated across independent reporting")).toBeInTheDocument();
    expect(screen.getByText("Publisher’s rating")).toBeInTheDocument();
    expect(screen.getByText("발표 확인")).toBeInTheDocument();
    expect(screen.getByText("Reported statement")).toBeInTheDocument();
    expect(screen.getByText("No reliable page date")).toBeInTheDocument();
    expect(screen.getByText("Exact claim match")).toBeInTheDocument();
    expect(screen.getByText("Why it matters:")).toBeInTheDocument();
    expect(screen.getByText("What changed across languages")).toBeInTheDocument();
    expect(screen.getByText("The Korean report names the agency directly.")).toBeInTheDocument();
    expect(screen.getByText("Credits The agency")).toBeInTheDocument();
    expect(
      screen.getByText("This supports the attribution, not the underlying allegation.")
    ).toBeInTheDocument();
    expect(screen.queryByText("[evidence-1]")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open source ↗" })).toHaveAttribute(
      "href",
      "https://check.example/report"
    );
  });

  it("does not hide partial retrieval failures", () => {
    render(FactCheckResults, { job });

    expect(screen.getByText("Some sources could not be checked")).toBeInTheDocument();
  });

  it("shows the search scope and explains an unresolved result", () => {
    const unresolvedJob = structuredClone(job);
    const claimResult = unresolvedJob.result!.claims[0];
    claimResult.assessment.status = "insufficient";
    claimResult.trace!.evidence_state = "unresolved";
    claimResult.assessment.explanation = "One relevant report was found.";
    claimResult.assessment.limitations = [
      "Fewer than two independent evidence clusters were found.",
      "Fewer than two distinct publishers were found."
    ];

    render(FactCheckResults, { job: unresolvedJob });

    expect(screen.getAllByText("Still unresolved")).toHaveLength(2);
    expect(screen.getByText("One relevant report was found.")).toBeInTheDocument();
    expect(screen.getByText("What we could establish")).toBeInTheDocument();
    expect(screen.getByText("See what was searched")).toBeInTheDocument();
    expect(screen.getByText("\"버스 24대\" 기관")).toBeInTheDocument();
    expect(screen.getByText("Evidence excerpts")).toBeInTheDocument();
  });

  it("does not imply wording equivalence when no passage aligned reliably", () => {
    const unresolvedJob = structuredClone(job);
    const claimResult = unresolvedJob.result!.claims[0];
    claimResult.assessment.status = "insufficient";
    claimResult.trace!.evidence_state = "unresolved";
    claimResult.evidence[0].alignment_state = "uncertain";
    claimResult.evidence[0].aligned_quote = null;
    claimResult.trace!.meaning_deltas = [];

    render(FactCheckResults, { job: unresolvedJob });

    expect(
      screen.getByText(
        "No cross-language passage was aligned reliably enough to compare wording."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Match uncertain")).toBeInTheDocument();
    expect(
      screen.queryByText("No material wording difference was identified in the aligned passages.")
    ).not.toBeInTheDocument();
  });

  it("explains why repeated articles count as one lineage", () => {
    const repeatedJob = structuredClone(job);
    const claimResult = repeatedJob.result!.claims[0];
    const repeated = {
      ...claimResult.evidence[0],
      id: "evidence-2",
      url: "https://copy.example/report",
      publisher: "Copy Desk"
    };
    claimResult.evidence.push(repeated);
    claimResult.assessment.support_evidence_ids.push("evidence-2");
    claimResult.trace!.article_count = 2;
    claimResult.trace!.independent_lineages = 1;

    render(FactCheckResults, { job: repeatedJob });

    expect(
      screen.getByText(
        "2 articles count as 1 independent lineage because credited or repeated reporting was grouped together."
      )
    ).toBeInTheDocument();
  });

  it("puts supporting and challenging evidence side by side for mixed results", () => {
    const mixedJob = structuredClone(job);
    const claimResult = mixedJob.result!.claims[0];
    const challenge = {
      ...claimResult.evidence[0],
      id: "evidence-2",
      url: "https://challenge.example/report",
      publisher: "Challenge Desk",
      publisher_key: "challenge.example",
      cluster_id: "challenge-cluster",
      stance: "disputes" as const,
      stance_reason: "The report gives a different date."
    };
    claimResult.evidence.push(challenge);
    claimResult.assessment.status = "mixed";
    claimResult.trace!.evidence_state = "conflicting";
    claimResult.assessment.challenge_evidence_ids = ["evidence-2"];

    render(FactCheckResults, { job: mixedJob });

    expect(screen.getByText("Agrees with the claim")).toBeInTheDocument();
    expect(screen.getByText("Challenges the claim")).toBeInTheDocument();
    expect(screen.getByText("Sources differ on a material detail")).toBeInTheDocument();
  });
});
