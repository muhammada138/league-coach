1.  **Analyze the Gap**: `frontend/src/api/riot.js` exposes `getLiveEnrich` which wraps a `POST` request to `api.post("/live-enrich")` using Axios. The issue explicitly asked for it to be tested and mentioned "Testing a simple fetch wrapper requires basic fetch mocking with POST method." (Note: The provided current code actually shows a `fetch` wrapper in the task details but the real file uses `axios`. The intention is the same: to mock the network request).
2.  **Plan Test Strategy**:
    *   Framework: `vitest` with `@testing-library/react` (based on `App.test.jsx` and `package.json`).
    *   Patterns: Use `vi.mock('axios')` to mock the axios instance, interceptors, and post method.
    *   Scenarios:
        *   Calling `getLiveEnrich` with default arguments (`queueId=420`, `region="na1"`).
        *   Calling `getLiveEnrich` with explicit arguments.
        *   Checking if the function correctly returns `.data`.
3.  **Implement**: Write the test file `frontend/src/api/riot.test.js` using the created mock. (Already done basically to verify).
4.  **Verify**: Run `npm test -- src/api/riot.test.js` in the `frontend` dir to ensure it passes. Also run `npm test` on the whole suite.
5.  **Pre-commit steps**: Run pre commit instructions to make sure proper testing, verifications, reviews and reflections are done.
6.  **Submit**: Commit and submit with the specified PR title and description.
