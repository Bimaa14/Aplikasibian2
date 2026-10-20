export const NOTE_PRINT_STYLES = `
  * { text-shadow: none; -webkit-text-stroke-width: 0; }
  body { font-synthesis: none; }
  .bank-account { margin: 1mm 0 0; font-size: 10pt; line-height: 1.2; break-inside: avoid; text-align: left; }
  .bank-account p { margin: 0; }
  .bank-account .account-holder { margin-top: .5mm; }
`;

export const NOTE_BANK_ACCOUNT = `<section class="bank-account" aria-label="Rekening pembayaran">
  <p>Bank BCA</p>
  <p>3761155405</p>
  <p class="account-holder">A.N Wati Wulandari</p>
</section>`;
