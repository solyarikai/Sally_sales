/** Convert HTML email to clean readable text */
export function stripHtml(raw: string): string {
  if (!raw) return '';
  // If no tags at all, just clean up the plain text
  if (!raw.includes('<')) return cleanPlainText(raw);

  try {
    const doc = new DOMParser().parseFromString(raw, 'text/html');

    // Remove <style>, <script>, <head> entirely
    doc.querySelectorAll('style, script, head').forEach(el => el.remove());

    // Remove common signature / disclaimer containers
    doc.querySelectorAll(
      '[class*="gmail_signature"], [class*="signature"], [data-smartmail]'
    ).forEach(el => el.remove());

    // Remove quoted email chains (gmail_quote, blockquote, mso-reply)
    doc.querySelectorAll(
      '[class*="gmail_quote"], [class*="gmail_extra"], blockquote[type="cite"], ' +
      '[class*="yahoo_quoted"], [class*="moz-cite-prefix"], [id*="replySplit"]'
    ).forEach(el => el.remove());

    // Walk the DOM, converting block elements to \n
    const text = domToText(doc.body);
    return cleanPlainText(text);
  } catch {
    // Fallback: regex approach
    let text = raw;
    // Block elements → newline
    text = text.replace(/<\s*(br|\/div|\/p|\/tr|\/li|\/h[1-6])\s*\/?>/gi, '\n');
    // All remaining tags → nothing
    text = text.replace(/<[^>]*>/g, '');
    // Decode common entities
    text = decodeEntities(text);
    return cleanPlainText(text);
  }
}

/** Recursively extract text from DOM, inserting newlines for block elements */
const BLOCK_TAGS = new Set([
  'DIV', 'P', 'BR', 'TR', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'BLOCKQUOTE', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'HR', 'UL', 'OL',
  'TABLE', 'THEAD', 'TBODY',
]);

function domToText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent || '';
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const el = node as HTMLElement;
  const tag = el.tagName;

  // Skip hidden elements
  if (el.style.display === 'none' || el.getAttribute('aria-hidden') === 'true') return '';
  // Skip images (often tracking pixels)
  if (tag === 'IMG') return '';

  let result = '';
  const isBlock = BLOCK_TAGS.has(tag);

  if (tag === 'BR') return '\n';
  if (tag === 'HR') return '\n---\n';

  if (isBlock) result += '\n';

  for (const child of Array.from(node.childNodes)) {
    result += domToText(child);
  }

  if (isBlock) result += '\n';
  return result;
}

function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#x27;/gi, "'");
}

/** Clean up plain text: trim signatures, disclaimers, quoted chains, collapse whitespace */
function cleanPlainText(text: string): string {
  // Decode HTML entities that might remain (including &lt; &gt; common in plain-text emails)
  text = decodeEntities(text);

  // Normalize line endings
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // Trim each line
  text = text.split('\n').map(l => l.trimEnd()).join('\n');

  // Collapse 3+ blank lines into 2
  text = text.replace(/\n{3,}/g, '\n\n');

  // Cut at first matching marker (works on both multi-line and single-line text)
  const cutMarkers = [
    // Quoted reply chains (most common patterns)
    /On [A-Z][a-z]{2,8},?\s.{5,80}\s+wrote:\s*/i,
    /El [a-z]{2,10},?\s.{5,80}\s+escribi[oó]:\s*/i,
    /Le [a-z]{2,10},?\s.{5,80}\s+[aà] [eé]crit\s*:\s*/i,
    /Am [A-Z0-9].{5,80}\s+schrieb\s*.*:\s*/i,
    /\d{1,2}\/\d{1,2}\/\d{2,4}.{0,60}wrote/i,
    /-{2,}\s*Original Message\s*-{2,}/i,
    // Outlook-style email headers (English)
    /\nFrom:\s.{3,80}\n\s*Sent:\s/i,
    /\nFrom:\s.{3,80}\n\s*Date:\s/i,
    // Outlook-style email headers (Russian)
    /\nОт:\s/i,
    /\nОтправлено:\s/i,
    // Forwarded messages
    /-{5,}\s*Forwarded message\s*-{5,}/i,
    // Disclaimers / confidentiality
    /AVISO DE CONFIDENCIALIDAD/i,
    /CONFIDENTIALITY NOTICE/i,
    /This email and any attachments? (?:are|is) confidential/i,
    /CONSULTE NUESTRO AVISO/i,
    /_{10,}/,
    // Eco-friendly disclaimers (common in LATAM emails)
    /Cuidemos nuestro planeta/i,
    /Este correo electr[oó]nico y cualquier archivo/i,
  ];

  let earliest = text.length;
  for (const marker of cutMarkers) {
    const match = text.match(marker);
    if (match && match.index !== undefined && match.index > 20 && match.index < earliest) {
      earliest = match.index;
    }
  }
  if (earliest < text.length) {
    text = text.substring(0, earliest).trimEnd();
  }

  return text.trim();
}
