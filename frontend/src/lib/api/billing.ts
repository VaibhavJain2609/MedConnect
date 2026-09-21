/**
 * Billing API helpers.
 *
 * List/detail fetchers for the patient portal live in `patient-portal.ts`
 * (`getMyBills`, `getMyBill`, `PatientBill`). This module holds helpers that
 * aren't patient-portal-specific — currently the PDF receipt/invoice
 * download, which goes through `downloadFile` so the request carries the
 * axios Bearer-token interceptor.
 */

import { downloadFile, openFileInNewTab } from "../download";

export function billReceiptUrl(billId: string, download = false): string {
  return `/api/v1/billing/${billId}/receipt${download ? "?download=true" : ""}`;
}

/** Download the PDF receipt (paid) or invoice (unpaid) for a bill. */
export async function downloadBillReceipt(billId: string): Promise<void> {
  await downloadFile(billReceiptUrl(billId, /* download */ true));
}

/** Open the bill's PDF receipt/invoice in a new browser tab. */
export async function openBillReceiptInNewTab(billId: string): Promise<void> {
  await openFileInNewTab(billReceiptUrl(billId));
}
