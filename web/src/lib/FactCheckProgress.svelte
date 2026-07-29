<script lang="ts">
  import type { FactCheckJob } from "./types";

  export let job: FactCheckJob;
</script>

<div class="claim-progress fact-check-progress" aria-live="polite" aria-busy="true">
  <p class="progress-kicker">Claim Trace</p>
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
  <p>
    Finding related reporting, grouping repeated source material, and comparing how
    your claim changes across languages.
  </p>
  <p class="progress-footnote">You can return to this URL while the check runs. Unreadable sources will be listed in the result.</p>
</div>
