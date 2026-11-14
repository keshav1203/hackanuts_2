// Must match the stage names the backend pipeline reports.
export const STEPS = [
  "Cloning repository",
  "Detecting language and framework",
  "Scanning code, queries and architecture",
  "Running Code Analysis Agent",
  "Running Performance Agent",
  "Running Optimization Agent",
];

export const GITHUB_RE = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+?(\.git)?\/?$/i;
