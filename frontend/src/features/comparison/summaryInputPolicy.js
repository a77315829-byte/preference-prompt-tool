// Match Python len(str): Unicode code points, including whitespace; never slice.
export const SUMMARY_DOMAINS = ['summarization', 'summarization_ko', 'summarization_hybrid'];
export const MAX_SOURCE_CHARS = 12000;
export const MAX_TOPIC_CHARS = 300;
export const characterCount = (text) => Array.from(text).length;
export const isSummaryDomain = (key) => SUMMARY_DOMAINS.includes(key);
export const sourceTooLong = (text) => characterCount(text) > MAX_SOURCE_CHARS;
