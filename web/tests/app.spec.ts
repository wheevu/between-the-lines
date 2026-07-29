import { expect, test } from "@playwright/test";

test("supports keyboard users with a skip link and visible main target", async ({ page }) => {
  await page.goto("/");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.locator("main")).toBeFocused();
});

test("shows a clear empty-state validation message", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Translate to Vietnamese" }).click();

  await expect(page.getByRole("alert")).toHaveText("Add an article URL first.");
});

test("completes a quick translation review and records feedback", async ({ page }, testInfo) => {
  const feedbackBodies: unknown[] = [];
  const analysisBodies: unknown[] = [];
  const completedJob = {
    id: "analysis-1",
    status: "complete",
    stage: "Ready to review",
    progress: 100,
    error: null,
    result: {
      source_language: "en",
      source_title: null,
      source_url: null,
      segments: [
        {
          id: "p1s1",
          paragraph_index: 0,
          sentence_index: 0,
          source_text: "Officials said the policy may begin in September.",
          translations: [
            {
              language: "vi",
              text: "Các quan chức cho biết chính sách có thể bắt đầu vào tháng 9.",
              shadow_text: null,
              similarity: null,
              back_translation_similarity: null,
              flags: [
                {
                  id: "flag-meaning",
                  target_language: "vi",
                  kind: "meaning-risk",
                  category: "modality",
                  confidence: "medium",
                  source_quote: "may",
                  translation_quote: "có thể",
                  explanation: "The degree of certainty deserves a closer read.",
                  alternative: null,
                  signals: ["Gemini identified a translation choice"]
                }
              ]
            }
          ]
        }
      ]
    }
  };

  await page.route("**/api/analyses", async (route) => {
    analysisBodies.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        id: "analysis-1",
        status: "queued",
        stage: "Waiting to start",
        progress: 0,
        result: null,
        error: null
      },
      status: 202
    });
  });
  await page.route("**/api/analyses/analysis-1/feedback", async (route) => {
    const feedbackBody = route.request().postDataJSON();
    feedbackBodies.push(feedbackBody);
    await route.fulfill({
      json: { id: "feedback-1", analysis_id: "analysis-1", ...feedbackBody }
    });
  });
  await page.route("**/api/analyses/analysis-1", async (route) => {
    await route.fulfill({ json: completedJob });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Paste text" }).click();
  await page.getByLabel("Article text").fill(completedJob.result.segments[0].source_text);
  await page.getByRole("button", { name: "Translate to Vietnamese" }).click();

  await expect.poll(() => analysisBodies[0]).toEqual({
    source_language: "en",
    target_language: "vi",
    text: completedJob.result.segments[0].source_text
  });
  await expect(page).toHaveURL(/analysis=analysis-1/);
  await expect(page.getByRole("heading", { name: "Translation ready" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "1 passage worth checking" })).toBeVisible();
  await expect(page.getByText("The degree of certainty deserves a closer read.")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("review.png"), fullPage: true });

  await page
    .locator(".flag-detail")
    .filter({ hasText: "The degree of certainty deserves a closer read." })
    .getByRole("button", { name: "Yes" })
    .click();
  await expect.poll(() => feedbackBodies[0]).toEqual({
    flag_id: "flag-meaning",
    verdict: "helpful",
    reviewer_role: "unspecified"
  });

  const passageReview = page.locator(".passage-review");
  await passageReview.getByRole("button", { name: "No" }).click();
  await passageReview
    .getByLabel("What changed or went missing?")
    .fill("The Vietnamese translation sounds more certain than the source.");
  await passageReview.getByRole("button", { name: "Save review" }).click();

  await expect(passageReview.getByRole("status")).toHaveText("Review saved.");
  await expect.poll(() => feedbackBodies[1]).toEqual({
    flag_id: "__overall__:vi",
    verdict: "incorrect",
    correction: "The Vietnamese translation sounds more certain than the source.",
    reviewer_role: "unspecified"
  });
});

test("restores a completed analysis from its URL", async ({ page }) => {
  await page.route("**/api/analyses/analysis-saved", async (route) => {
    await route.fulfill({
      json: {
        id: "analysis-saved",
        status: "complete",
        stage: "Ready to review",
        progress: 100,
        error: null,
        result: {
          source_language: "vi",
          source_title: "Saved article",
          source_url: null,
          segments: [
            {
              id: "p1s1",
              paragraph_index: 0,
              sentence_index: 0,
              source_text: "Bài viết đã lưu.",
              translations: [
                {
                  language: "en",
                  text: "A saved article.",
                  shadow_text: null,
                  similarity: 0.95,
                  back_translation_similarity: null,
                  flags: []
                },
                {
                  language: "ko",
                  text: "저장된 기사.",
                  shadow_text: null,
                  similarity: 0.94,
                  back_translation_similarity: null,
                  flags: []
                }
              ]
            }
          ]
        }
      }
    });
  });

  await page.goto("/?analysis=analysis-saved");

  await expect(page.getByRole("heading", { name: "Saved article" })).toBeVisible();
  await expect(page.getByText("A saved article.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose a claim to trace" })).toHaveCount(0);
});

test("starts Claim Trace from a completed translation", async ({ page }) => {
  const factCheck = {
    id: "fact-check-new",
    analysis_id: "analysis-saved",
    status: "awaiting_selection",
    stage: "Choose claims to check",
    progress: 100,
    error: null,
    selected_candidate_ids: [],
    result: null,
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
        reason: "A specific attributed number can be traced."
      }
    ]
  };
  await page.route("**/api/analyses/analysis-saved", async (route) => {
    await route.fulfill({
      json: {
        id: "analysis-saved",
        status: "complete",
        stage: "Ready to review",
        progress: 100,
        error: null,
        result: {
          source_language: "en",
          source_title: "Saved article",
          source_url: null,
          segments: [
            {
              id: "p1s1",
              paragraph_index: 0,
              sentence_index: 0,
              source_text: "The agency reported 20 cases.",
              translations: [
                {
                  language: "vi",
                  text: "Cơ quan báo cáo 20 trường hợp.",
                  shadow_text: null,
                  similarity: 0.95,
                  back_translation_similarity: null,
                  flags: []
                },
                {
                  language: "ko",
                  text: "기관은 20건을 보고했다.",
                  shadow_text: null,
                  similarity: 0.94,
                  back_translation_similarity: null,
                  flags: []
                }
              ]
            }
          ]
        }
      }
    });
  });
  await page.route("**/api/analyses/analysis-saved/fact-checks", async (route) => {
    await route.fulfill({ json: factCheck, status: 202 });
  });
  await page.route("**/api/fact-checks/fact-check-new", async (route) => {
    await route.fulfill({ json: factCheck });
  });

  await page.goto("/?analysis=analysis-saved&reviewer=author");
  await page.getByRole("button", { name: "Choose a claim to trace" }).click();

  await expect(page).toHaveURL(/fact_check=fact-check-new/);
  await expect(page.getByRole("heading", { name: "Which claim should we follow?" })).toBeVisible();
});

test("restores claim selection without choosing anything for the reader", async ({ page }) => {
  const selections: unknown[] = [];
  const factCheck = {
    id: "fact-check-saved",
    analysis_id: "analysis-saved",
    status: "awaiting_selection",
    stage: "Choose claims to check",
    progress: 100,
    error: null,
    selected_candidate_ids: [],
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
        reason: "A specific attributed number can be checked."
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
  await page.route("**/api/fact-checks/fact-check-saved", async (route) => {
    await route.fulfill({ json: factCheck });
  });
  await page.route("**/api/fact-checks/fact-check-saved/selection", async (route) => {
    selections.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        ...factCheck,
        selected_candidate_ids: ["claim-1"],
        stage: "Claims selected; evidence search is still gated"
      }
    });
  });

  await page.goto("/?fact_check=fact-check-saved&reviewer=independent");

  await expect(page.getByRole("heading", { name: "Which claim should we follow?" })).toBeVisible();
  const radios = page.getByRole("radio");
  await expect(radios.nth(0)).not.toBeChecked();
  await expect(radios.nth(1)).toBeDisabled();

  await radios.nth(0).check();
  await page.getByRole("button", { name: "Trace this claim" }).click();

  await expect(page.locator(".claim-actions").getByRole("status")).toHaveText("Selection saved.");
  await expect.poll(() => selections[0]).toEqual({ candidate_ids: ["claim-1"] });
});

test("resumes an evidence check and keeps source feedback attached to its excerpt", async ({
  page
}, testInfo) => {
  const feedbackBodies: unknown[] = [];
  let reads = 0;
  const baseJob = {
    id: "fact-check-running",
    analysis_id: "analysis-saved",
    progress: 72,
    candidates: [],
    selected_candidate_ids: ["claim-1"],
    error: null
  };
  const completedJob = {
    ...baseJob,
    status: "complete",
    stage: "Evidence ready to inspect",
    progress: 100,
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
            reason: "A checkable attributed figure."
          },
          queries: [],
          evidence: [
            {
              id: "evidence-1",
              url: "https://source.example/report",
              title: "The agency’s report",
              publisher: "Source Desk",
              language: "en",
              excerpt: "The agency said that the trial included 24 buses.",
              source_type: "direct-reporting",
              rating: null,
              published_at: null,
              retrieved_at: "2026-07-24T09:55:00Z",
              content_hash: "hash",
              cluster_id: "cluster",
              relevance: 0.93,
              stance: "supports",
              stance_reason: "The report attributes the same figure to the agency.",
              direct: false,
              mismatch: null
            }
          ],
          assessment: {
            claim_id: "claim-1",
            status: "insufficient",
            explanation: "Only one independent report was available.",
            support_evidence_ids: ["evidence-1"],
            challenge_evidence_ids: [],
            context_evidence_ids: [],
            limitations: ["One source does not meet the confirmation rule."]
          },
          retrieval_failures: [],
          error: null
        }
      ]
    }
  };

  await page.route("**/api/fact-checks/fact-check-running", async (route) => {
    reads += 1;
    await route.fulfill({
      json:
        reads === 1
          ? {
              ...baseJob,
              status: "ranking",
              stage: "Ranking evidence for claim 1 of 1",
              result: null
            }
          : completedJob
    });
  });
  await page.route("**/api/fact-checks/fact-check-running/feedback", async (route) => {
    const body = route.request().postDataJSON();
    feedbackBodies.push(body);
    await route.fulfill({
      json: {
        id: "feedback-1",
        fact_check_id: "fact-check-running",
        ...body
      }
    });
  });

  await page.goto("/?fact_check=fact-check-running&reviewer=independent");

  await expect(page.getByRole("heading", { name: "Ranking evidence for claim 1 of 1" })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "72");
  await expect(page.locator(".assessment-status")).toHaveText("Still unresolved");
  await expect(page.getByText("The agency’s report")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("evidence-result.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("evidence-result-mobile.png"),
    fullPage: true
  });

  await page
    .locator(".evidence-card")
    .getByRole("button", { name: "Yes" })
    .click();

  await expect(page.locator(".evidence-card").getByRole("status")).toHaveText("Feedback saved.");
  await expect.poll(() => feedbackBodies[0]).toEqual({
    target_type: "evidence",
    target_id: "evidence-1",
    verdict: "helpful"
  });
});
