# UI and browser quality

Use this guidance when changing the Samples, Data Locations, Queue, Failures,
Checkout, or Monitor pages. Keep the implementation small, direct, and consistent
with the existing Django templates and shared browser code.

## Product expectations

- Keep the interface quiet and information-dense. Use the existing cards, buttons,
  status pills, tags, disclosure panels, table footers, and spacing tokens.
- Use direct labels such as `Fastq Name`, `Load Name`, `Batch Name From Vendor`,
  `Organism Common Name`, `Library Prep Method`, `Stage`, `Status`, `Duration`,
  and `Demand ID`.
- Do not add duplicate labels, decorative panels, unexplained badges, or a second
  component for a pattern that already exists.
- Keep table widths adjustable through the existing column-resize behavior. The
  rightmost column must absorb the minimum table width rather than leaving a large
  blank area beside the table.
- Keep table height driven by its rows and footer. Do not add viewport-height
  spacers or fixed heights that create empty space after the last row.
- Keep horizontal scrolling inside the table container. Do not make the whole page
  wider than the viewport because a table has many columns.
- Place pagination in the shared table footer. Keep the rows-per-page selector,
  range, and previous/next controls aligned as one unit.
- Use the shared pagination partial for Samples, Data Locations, Checkout, Monitor,
  and other paginated tables. Preserve the current query parameters when changing
  page or page size.

## Shared components

Extend existing partials and scripts before creating new ones.

- Use `partials/table_pager.html` for page size, range, and navigation.
- Use `partials/sync_status.html` for the `Sync just now` or `Sync 3m ago`
  indicator. Do not write `Synced just now ago` or create a page-specific variant.
- Use the shared study-set filter for Samples and Data Locations. It must support
  multiple selections, show whether selections are active, provide one control that
  toggles between selecting all and selecting none, and apply the selected values to
  the table query.
- Use the shared multi-value filter for Batch Name From Vendor, Organism Common Name,
  and Library Prep Method. The selected values must affect the table, not only the
  button summary.
- Use the shared column menu for the Samples and Data Locations exports. CSV export
  must include only the columns currently shown and only the rows in the current tab
  and filter scope.
- Use the existing disclosure behavior for More Filters, credential details, S3
  contents, and log panels. Use delegated events because these regions can be
  replaced by polling.
- Use the existing status badge, copy-value, submission-source, and tag partials
  instead of duplicating their markup or colors.

## Filters and menus

- A search for Fastq Name, Load Name, or Batch Name From Vendor must submit with
  Enter. Keep an Apply Filters control when the form has several filters so users can
  submit all changes together.
- Data Locations must offer a stage filter for Ingest, Alignment, and Post-alignment.
  It must not offer Export when the page has no export location data.
- Samples and Data Locations must allow multiple study sets and multiple values in
  the three multi-value filters. A selection is not complete until the table query
  reflects it.
- Use `All` consistently for an unfiltered value. Do not mix `all`, `Any status`,
  and other near-duplicate labels in the same control unless the field genuinely
  needs a different meaning.
- Keep dropdowns above the table or pinned inside the viewport when there is not
  enough room below the trigger. They must not render behind table rows, extend the
  page to an unexpected height, or clip their options.
- A focused or opened select must not remain with an unintended dark background.
  The border, arrow, and focus treatment should match the other filter controls.
- When a menu closes, restore its draft selection only if the user did not apply it.
  Do not silently change the table while the user is still choosing values.

## Polling and refresh behavior

Polling reads the local Django database. AWS synchronization is a separate explicit
operation and must not be triggered by every browser poll.

- Monitor polls its table fragment about every 30 seconds. It updates the local
  table data without navigating or refreshing the document.
- Monitor duration is calculated in the browser from the stored `started_at` value.
  Update it at minute boundaries and display minutes, hours, and days, not seconds.
- Queue and Failures use the shared fragment polling behavior. Samples and Data
  Locations use targeted status polling so active filters, selections, resized
  columns, and expanded S3 contents remain intact.
- The page must skip a poll while the document is hidden and must not start a second
  request while the first request is in flight.
- A failed poll keeps the last successful DOM. It must not clear a table, redirect
  the user, or show a false empty state.
- Replace only the intended live region. Keep credential forms, user input, open
  disclosures, and other state outside that region when they must survive polling.
- Manual AWS sync buttons must clearly say what they sync, use the current page scope,
  and update the shared sync indicator after the server response. They must not be
  confused with the local database polling indicator.
- A normal filter, pagination, or form submission may navigate when that is the
  established server-rendered behavior. Automatic polling must not navigate.

## Refresh race conditions

Treat every poll response as stale until it has passed the state checks required by
the component receiving it.

- Guard each polling loop with an in-flight flag. Clear it in `finally`.
- Read and validate the complete response before dispatching the pre-refresh event or
  replacing DOM nodes. A failed response body must not cancel an active log request.
- Dispatch `joblog:before-refresh` immediately before replacing a live region and
  `joblog:refreshed` after the replacement and state restoration.
- Before replacement, capture open log panel demand IDs and their rendered bodies.
  Restore only panels that still exist in the new response.
- Abort active log requests before replacing their body nodes. Record only the demand
  IDs that were actually interrupted by that refresh.
- Retry an interrupted log request after refresh only when its panel is still open,
  the request has not been cleared, and the session credentials are still valid.
- Ignore a log response when its request is no longer the current request for that
  demand, its body is detached, or its panel is closed.
- Closing a log panel cancels its request. Clearing credentials cancels every request
  and must prevent any retry.
- Do not use per-element `data-bound` flags for listeners on polled content. Delegate
  clicks from a stable ancestor such as `document` so newly inserted buttons work.
- Do not let a table refresh disable eye buttons permanently. After replacement,
  re-enable them when the credential session is valid.
- Do not fetch logs merely because a table refresh occurred. Fetch logs only when the
  user opens a row or when a user-open panel's request was interrupted by replacement.

## Log panel and eye icon

- The eye icon is a row action for container logs. It is disabled until the user has
  validated temporary credentials for this session.
- The eye button must open and close the row panel, update `aria-expanded`, and use a
  folder or eye state that makes the open state clear. Its tooltip appears on hover,
  not as a fixed overlay that follows the page while scrolling.
- Keep the row log panel closed by default. A closed panel must not contribute a large
  empty table row or page-height gap.
- Render log lines in chronological order starting at the beginning of the container
  log stream. Keep the viewer scrolled at the top when it opens; do not silently jump
  to the newest line.
- Show a short loading state only after the user opens the panel. Do not repeatedly
  refresh the same log panel every few seconds.
- Show clear outcomes for no credentials, unavailable logs, expired credentials, and
  failed credentials. Do not render a traceback or secret value in the page.
- Credential state uses these visible labels: `Credentials required`, `Credentials
  valid`, `Credentials expired`, and `Credentials failed`. Use one simple `Validate
  credentials` action and one `Clear` action. Do not add a `Replace` action.
- Temporary credentials are used only by the log-viewing request. They are validated
  server-side, stored only for the current session, and must never be used for queue
  submission, AWS synchronization, or any other app operation. Never place secret
  values in templates, JavaScript, logs, tests, screenshots, or this file.

## Queue and failure behavior

- Queue polling shows the current local queue without delaying or reordering a worker
  submission. User pause state is applied when the worker chooses the next job, so a
  paused user's jobs are skipped and the next eligible user's job can run.
- A user can pause their own queue and delete their own pending rows. Do not expose
  another user's queue controls to a non-staff user.
- Failures must distinguish OmicsHub submission failures from OCS execution failures.
  Keep the page scoped to failures created or managed by OmicsHub.
- A failed execution row can show the log eye action when the demand is visible and
  its log mapping is available. A missing execution or log stream is a clear row
  message, not a page error or a repeated request loop.

## Playwright acceptance tests

Run browser tests against a real Django live server and Chromium. Use fake credentials
and mocked AWS clients at the application boundary. Never use real access keys or
session tokens in tests.

At minimum, cover these observable behaviors:

1. Open Samples and Data Locations at desktop and narrow widths. Confirm the table
   stays inside its scroll container, the footer has no large blank area, and the
   pager remains usable.
2. Select several study sets and several values in each multi-value filter. Apply the
   form and confirm every selected value is reflected in the request and table rows.
3. Open More Filters near the bottom of the viewport. Confirm the menu stays visible,
   has usable scrolling, and does not render behind table rows. Confirm `All` is the
   unfiltered label.
4. Change rows per page and next/previous pages on Samples, Data Locations, Checkout,
   and Monitor. Confirm the range, table rows, and query parameters agree.
5. Resize several columns, including the rightmost column. Confirm widths persist for
   the table and no unexplained empty area appears beside it.
6. On Monitor, validate fake temporary credentials, open a running log panel, trigger
   a poll while the log request is pending, and confirm the panel stays open, the old
   request cannot overwrite the new body, and exactly one retry is made.
7. After a poll replaces Monitor or Failures table HTML, click a new eye button. Confirm
   it still opens, fetches once, and closes. Clear credentials and confirm every eye
   button becomes disabled.
8. Close a log panel while its request is pending. Confirm the response is ignored and
   no detached panel is updated. Clear credentials during a request and confirm no
   retry occurs.
9. Confirm polling does not navigate or reload the document, skips while the tab is
   hidden, and does not create overlapping requests.
10. Confirm log output starts at the oldest returned event, the viewer starts at
    scroll position zero, and repeated table polling does not refetch a closed panel.
11. Click a finished status, stage filter, sync icon, and eye icon independently.
    Each control must perform only its named action and must not submit an unrelated
    form or navigate unexpectedly.

Useful checks include the repository's Playwright monitor tests, the focused Django
template/view tests, JavaScript syntax checks, `git diff --check`, and the Docker
health endpoint when testing the running stack. Report environment blockers instead
of weakening or skipping a valid browser test.

## Review checklist

Before finishing a UI change, inspect the complete diff and confirm:

- The change uses an existing partial or browser pattern where one already exists.
- The live region, request ownership, and event ordering remain clear.
- No polling path uses AWS credentials implicitly.
- No credential or log error is exposed outside the log-viewing flow.
- No dead listener, duplicate helper, substitute path, or unused selector was added.
- The page remains usable after refresh, filtering, pagination, resizing, scrolling,
  opening and closing disclosures, and changing viewport size.
- Tests cover the user-visible race or interaction that motivated the change.
