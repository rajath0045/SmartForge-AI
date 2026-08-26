export type BoardLanguage = 'en' | 'kn' | 'ta';

export const boardTranslations: Record<BoardLanguage, Record<string, string>> = {
  en: {
    title: "Today's production board", subtitle: 'Simple shift instructions for operators and supervisors.', shift: 'Shift 1', current: 'Current job', next: 'Next', machine: 'Machine', order: 'Order', part: 'Part', quantity: 'Quantity', start: 'Start job', complete: 'Mark complete', changeover: 'Changeover', issue: 'Issue / action', noIssue: 'No issue — continue to plan', pieces: 'pcs', running: 'Running', ready: 'Ready', setup: 'Setup', held: 'Held', supervisor: 'Supervisor note', note: 'Confirm first-piece inspection before releasing full batch.',
  },
  kn: {
    title: 'ಇಂದಿನ ಉತ್ಪಾದನಾ ಫಲಕ', subtitle: 'ಆಪರೇಟರ್ ಮತ್ತು ಮೇಲ್ವಿಚಾರಕರಿಗೆ ಸರಳ ಶಿಫ್ಟ್ ಸೂಚನೆಗಳು.', shift: 'ಶಿಫ್ಟ್ 1', current: 'ಪ್ರಸ್ತುತ ಕೆಲಸ', next: 'ಮುಂದಿನದು', machine: 'ಯಂತ್ರ', order: 'ಆರ್ಡರ್', part: 'ಭಾಗ', quantity: 'ಪ್ರಮಾಣ', start: 'ಕೆಲಸ ಪ್ರಾರಂಭಿಸಿ', complete: 'ಪೂರ್ಣ ಎಂದು ಗುರುತಿಸಿ', changeover: 'ಸೆಟಪ್ ಬದಲಾವಣೆ', issue: 'ಸಮಸ್ಯೆ / ಕ್ರಮ', noIssue: 'ಸಮಸ್ಯೆ ಇಲ್ಲ — ಯೋಜನೆಯಂತೆ ಮುಂದುವರಿಸಿ', pieces: 'ತುಂಡುಗಳು', running: 'ಚಾಲನೆಯಲ್ಲಿದೆ', ready: 'ಸಿದ್ಧ', setup: 'ಸೆಟಪ್', held: 'ತಡೆಹಿಡಿದಿದೆ', supervisor: 'ಮೇಲ್ವಿಚಾರಕರ ಸೂಚನೆ', note: 'ಪೂರ್ಣ ಬ್ಯಾಚ್ ಬಿಡುಗಡೆಗೂ ಮೊದಲು ಮೊದಲ ಭಾಗದ ತಪಾಸಣೆ ಖಚಿತಪಡಿಸಿ.',
  },
  ta: {
    title: 'இன்றைய உற்பத்திப் பலகை', subtitle: 'ஆபரேட்டர்கள் மற்றும் மேற்பார்வையாளர்களுக்கான எளிய ஷிப்ட் வழிமுறைகள்.', shift: 'ஷிப்ட் 1', current: 'தற்போதைய வேலை', next: 'அடுத்தது', machine: 'இயந்திரம்', order: 'ஆர்டர்', part: 'பாகம்', quantity: 'அளவு', start: 'வேலையைத் தொடங்கு', complete: 'முடிந்ததாகக் குறி', changeover: 'அமைப்பு மாற்றம்', issue: 'சிக்கல் / நடவடிக்கை', noIssue: 'சிக்கல் இல்லை — திட்டப்படி தொடரவும்', pieces: 'பாகங்கள்', running: 'இயங்குகிறது', ready: 'தயார்', setup: 'அமைப்பு', held: 'நிறுத்தம்', supervisor: 'மேற்பார்வையாளர் குறிப்பு', note: 'முழுத் தொகுதியை விடுவிக்கும் முன் முதல் பாக ஆய்வை உறுதிசெய்யவும்.',
  },
};
