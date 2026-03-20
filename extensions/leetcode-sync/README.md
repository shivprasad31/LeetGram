# LeetGram LeetCode Sync Extension

This unpacked Chrome extension watches LeetCode submissions and sends accepted solutions to LeetGram.

## What It Does

- Detects LeetCode submit completion using a background service worker.
- Fetches the latest accepted submission from LeetCode GraphQL.
- Sends the accepted problem metadata and runtime/memory stats to LeetGram.
- Reuses the existing `ExternalProfileConnection`, `Problem`, and `UserSolvedProblem` models in this project.

## New Setup Flow

1. Sign in to LeetGram in the browser.
2. Open your profile edit page.
3. In the `LeetCode Extension` section, generate or rotate the extension token.
4. Copy the backend URL and token shown there.
5. Open the extension popup and save those two values.
6. Submit an accepted LeetCode solution.

## Backend Endpoints Used

- `GET/POST/PATCH /api/integrations/`
- `POST /api/integrations/{id}/issue-token/`
- `POST /api/integrations/leetcode/submissions/`

## Load It In Chrome

1. Open `chrome://extensions`.
2. Turn on Developer Mode.
3. Click Load unpacked.
4. Select the folder `extensions/leetcode-sync` from this repo.

## Notes

- Automatic sync currently targets accepted submissions on `https://leetcode.com/problems/*` pages.
- The implementation pattern was inspired by the LeetSync project, but this version posts into LeetGram instead of GitHub.
