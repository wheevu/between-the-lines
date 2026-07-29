<script lang="ts">
  import type { AnalysisJob } from "./types";

  export let job: AnalysisJob;
  export let onBack: () => void;
</script>

<section class="progress-view" aria-live="polite" aria-busy="true">
  <p class="progress-kicker">Working on your article</p>
  <h1>{job.stage}</h1>
  <div class="progress-line">
    <div
      class="progress-track"
      role="progressbar"
      aria-label={job.stage}
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={job.progress}
    >
      <div class="progress-value" style={`width: ${job.progress}%`}></div>
    </div>
    <span>{job.progress}%</span>
  </div>
  <p class="progress-detail">
    Full articles usually take 1–3 minutes on this Mac. You can refresh this page; the analysis
    link will bring you back here.
  </p>
  <button class="text-action" type="button" on:click={onBack}>Back to the article</button>
  <p class="progress-footnote">Work already sent to the models may continue in the background.</p>
</section>
