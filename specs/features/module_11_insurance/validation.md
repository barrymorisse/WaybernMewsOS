# validation.md — Module 11: Insurance Documents

## Validation Criteria

### Functional Tests

- [ ] Can create a new insurance policy with label, insurer name, cover dates, and total premium
- [ ] Policy appears in the insurance list after creation
- [ ] Can upload a PDF document and link it to a policy
- [ ] Uploaded PDF is saved to `documents/insurance/` on disk
- [ ] Extracted text contains `[Page N]` markers and is coherent
- [ ] Key facts card appears on the policy detail page after first document upload
- [ ] Key facts card updates when additional documents are uploaded
- [ ] Can ask a plain-language question and receive a grounded answer
- [ ] Answer contains at least one `[Page N]` citation
- [ ] Clicking "View PDF" opens the correct PDF inline in a new browser tab
- [ ] Clicking delete on a document shows a confirmation modal naming the document
- [ ] Cancelling the document delete modal leaves the document intact
- [ ] Confirming document delete removes the record, deletes the file from disk, and refreshes the document list and key facts card
- [ ] Clicking delete on a policy with documents shows a modal warning about cascade deletion, naming the document count
- [ ] Cancelling the policy delete modal leaves everything intact
- [ ] Confirming policy delete removes the policy, all linked documents, and all their files from disk
- [ ] "Insurance" sidebar link is present and navigates correctly
- [ ] Active state highlighted in sidebar when on any `/insurance` page

### Edge Case Tests

- [ ] Uploading an image-only (non-text) PDF shows a clear error and does not crash — document is saved but excluded from Q&A
- [ ] Policy with zero documents shows empty state on key facts card and disables chat input
- [ ] Groq API failure during key facts extraction: document is saved, key facts card shows partial/empty data gracefully
- [ ] Groq API failure during Q&A: friendly error message shown in chat response area
- [ ] Two documents with the same filename: second upload is saved with a timestamp suffix, no collision

### UX Validation

- [ ] Upload flow completes without a full page reload (HTMX partial swap)
- [ ] Chat response appears in-page without reload
- [ ] Key facts card is readable and scannable — not a wall of text
- [ ] Empty states are clear and instructive (not just blank)
- [ ] Document type labels are human-readable (not enum codes)

### Data Integrity

- [ ] Each `insurance_document` record is linked to exactly one `insurance_policy`
- [ ] `extracted_text` and `key_facts_json` are populated on successful upload
- [ ] Deleting a policy cascades to delete its documents (or is blocked if documents exist — decide at implementation)
- [ ] No duplicate document records created on double-submit

### Content Quality Check

- [ ] Key facts card correctly identifies insurer name, cover dates, and total premium from the real policy documents
- [ ] At least 3 of the main covers are correctly extracted
- [ ] Q&A answers for the following questions are accurate and cite correct pages:
  - "What is the total replacement value insured?"
  - "What is the excess for fire damage?"
  - "What does the SASRIA cover include?"
  - "What are the main exclusions on the policy?"

---

## Manual Test Script

Follow these steps in order to verify the feature from scratch.

**Setup**
1. Start the app (`./launch.sh` or `uvicorn main:app --reload`)
2. Navigate to `http://localhost:8000`
3. Confirm "Insurance" appears in the sidebar

**Create a policy**
4. Click "Insurance" in the sidebar
5. Click "New Policy"
6. Enter: Label = "2026–2027 Renewal", Insurer = [your insurer name], Cover Start = 2026-06-01, Cover End = 2027-05-31, Total Premium = [amount]
7. Submit — confirm you are redirected to the policy detail page
8. Confirm the policy header shows the correct details
9. Confirm the key facts card shows an empty state message
10. Confirm the chat input is disabled or shows "upload a document to enable Q&A"

**Upload documents**
11. Upload the renewal schedule PDF (name it "Renewal Schedule", type = renewal_schedule)
12. Wait for the page to update — confirm the document appears in the list with correct page count
13. Confirm the key facts card now shows at least: insurer name, cover dates, one cover type
14. Upload the main policy document PDF (name it "Policy Document", type = policy)
15. Confirm the key facts card updates and shows additional information (main covers, exclusions, excess)
16. Upload the SASRIA cover note (name it "SASRIA Cover Note", type = sasria)
17. Confirm all three documents appear in the list

**View PDFs**
18. Click "View PDF" on the renewal schedule — confirm it opens in a new tab and displays correctly
19. Click "View PDF" on the policy document — confirm it opens in a new tab

**Q&A**
20. Type into the chat box: "What is the total replacement value insured for the complex?"
21. Submit — confirm an answer appears with at least one `[Page N]` citation
22. Verify the page number cited is plausible (open the PDF and check that page)
23. Ask: "What is the excess for water damage?"
24. Ask: "What does the SASRIA cover include and exclude?"
25. Ask: "What happens if I need to make an emergency claim after hours?"
26. For each answer, confirm: (a) the answer is grounded in the documents, (b) page citations are present, (c) no hallucinated numbers appear

**Delete a document**
27. Click the delete button on the SASRIA cover note
28. Confirm a modal appears naming the document and warning that the action cannot be undone
29. Click Cancel — confirm the document is still in the list
30. Click delete again, then confirm — confirm the document disappears from the list
31. Confirm the file no longer exists in `documents/insurance/`
32. Confirm the key facts card refreshes (SASRIA-specific facts may be removed or reduced)

**Regression check**
31. Navigate to Units & Owners — confirm it loads correctly
32. Navigate to Meter Readings — confirm it loads correctly
33. Navigate to CoJ Invoices — confirm it loads correctly
