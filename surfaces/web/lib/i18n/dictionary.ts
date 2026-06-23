/* ============================================================================
   lib/i18n/dictionary.ts — the lightweight translation dictionary.

   Multilingual-by-design law: high-traffic surfaces read in the person's chosen
   language, with the STRUCTURE to add more languages and a parent able to read
   in their language. English is the source-of-truth and the fallback for any
   missing key (so a half-translated language never shows a blank).

   SUBJECT TERMINOLOGY IS NEVER ALTERED BY TRANSLATION. Subject names (e.g.
   "Mathematics", "Trigonometric Ratios") are NOT in this dictionary — they come
   from the ontology/engine and are rendered verbatim in every locale. Only the
   surrounding chrome (labels, prompts, calm copy) is translated.

   Coverage is honest: English is complete; Hindi covers auth (stepped), the role
   landing, settings, and the parent briefing/report. Untranslated keys fall back
   to English at runtime via t().
   ============================================================================ */

/** A supported locale code. Add a code here + a partial map below to extend. */
export type Locale = 'en' | 'hi';

/** The locale registry — code -> human label (in its own script) + direction. */
export interface LocaleMeta {
  code: Locale;
  /** The language name in its own script, for the calm switcher. */
  label: string;
  /** Text direction; all current locales are ltr. */
  dir: 'ltr' | 'rtl';
}

export const LOCALES: readonly LocaleMeta[] = [
  { code: 'en', label: 'English', dir: 'ltr' },
  { code: 'hi', label: 'हिन्दी', dir: 'ltr' },
];

export const DEFAULT_LOCALE: Locale = 'en';

/** Narrow an arbitrary string to a supported Locale, or the default. */
export function asLocale(value: string | undefined | null): Locale {
  return LOCALES.some((l) => l.code === value) ? (value as Locale) : DEFAULT_LOCALE;
}

/** The flat key space. Dotted keys group by surface; values are plain strings. */
export type Dictionary = Record<string, string>;

/* ----------------------------------------------------------------------------
   English — the COMPLETE source dictionary and the fallback for every locale.
   ---------------------------------------------------------------------------- */
const en: Dictionary = {
  // Common chrome
  'common.continue': 'Continue',
  'common.back': 'Back',
  'common.skipForNow': 'Skip for now',
  'common.signIn': 'Sign in',
  'common.createAccount': 'Create account',
  'common.on': 'On',
  'common.off': 'Off',

  // Auth (stepped)
  'auth.role.title': 'Who are you here as',
  'auth.role.sub': 'Classess shapes itself to you. You can change this later.',
  'auth.role.legend': 'Choose your role',
  'auth.identifier.titleSignUp': 'What is your email',
  'auth.identifier.titleSignIn': 'Welcome back',
  'auth.identifier.subPhone': 'We will text you a sign-in code.',
  'auth.identifier.subSignUp': 'You will use this to sign in.',
  'auth.identifier.subSignIn': 'Sign in to pick up where you left off.',
  'auth.email.label': 'Email',
  'auth.phone.label': 'Phone number',
  'auth.secret.titlePhone': 'Enter your code',
  'auth.secret.titleSignUp': 'Choose a password',
  'auth.secret.titleSignIn': 'Your password',
  'auth.secret.subSignUp': 'At least six characters.',
  'auth.password.label': 'Password',
  'auth.password.show': 'Show',
  'auth.password.hide': 'Hide',
  'auth.forgot': 'Forgot password',
  'auth.cta.createAccount': 'Create account',
  'auth.cta.verify': 'Verify and continue',
  'auth.switch.haveAccount': 'Already have an account?',
  'auth.switch.newHere': 'New to Classess?',
  'auth.demoNote':
    'Running in demo mode — your session is kept locally on this device, with no personal details stored.',
  'auth.forgot.title': 'Reset your password',
  'auth.forgot.sub': 'Enter your email and we will send a link to set a new password.',
  'auth.forgot.send': 'Send reset link',
  'auth.forgot.sent':
    'If an account exists for that email, a reset link is on its way. You can close this and check your inbox.',
  'auth.forgot.backToSignIn': 'Back to sign in',
  'auth.reset.title': 'Set a new password',
  'auth.reset.sub': 'Choose a new password to finish resetting your account.',
  'auth.reset.newLabel': 'New password',
  'auth.reset.set': 'Set new password',
  'auth.reset.done': 'Your password is set. You can sign in with it now.',
  'auth.reset.goSignIn': 'Go to sign in',

  // Personalise
  'personalise.title': 'A moment to shape your space',
  'personalise.sub':
    'A couple of natural taps, never a form. You can change any of this later in Settings.',
  'personalise.intent': 'What brings you in today',
  'personalise.subject': 'Pick a subject that looks interesting',
  'personalise.goal': 'What would you like to get from this',
  'personalise.language': 'Which language feels most comfortable',
  'personalise.footnote':
    'Each tap is a hint, not a form. I shape your space from these — you never have to describe yourself.',

  // Role landing
  'landing.homeSuffix': 'home',
  'landing.tryWithVidya': 'Try with Vidya',
  'landing.yourBriefing': 'Your briefing',
  'landing.quickLinks': 'Quick links',
  'landing.offline':
    'You are offline. The core flows still work; new conversations will sync when you reconnect.',

  // Settings
  'settings.eyebrow': 'Your preferences',
  'settings.title': 'Settings',
  'settings.howVidya': 'How Vidya helps and what it may read',
  'settings.language': 'Language',
  'settings.languageHelp':
    'Choose the language Classess reads back to you. Subject names stay the same in every language.',
  'settings.behaviouralNote':
    'Behavioural data is tied to an opaque identity, not to your name. You decide what is shared, and you can change it any time.',
  'settings.learned': 'What I learned about how you like to work',
  'settings.account': 'Account',
  'settings.reonboard': 'Re-run onboarding',
  'settings.signOut': 'Sign out',

  // Parent briefing / report
  'parent.reports.eyebrow': 'Reports',
  'parent.reports.whose': 'Whose reports',
  'parent.reports.sharedWithYou': 'Shared with you',
  'parent.reports.plainNote':
    'Each report is written for you, in plain language. No raw marks — just what is going well and the one next step that helps.',
  'parent.reports.releasedNote':
    'Reports are released to you by a teacher — never automatically. You see only what the school has chosen to share.',
  'parent.reports.celebrate': 'Celebrate',
  'parent.reports.nextStep': 'Next step',
  'parent.reports.sharedBy': 'Shared by',
  'parent.reports.email': 'Email this report',
  'parent.reports.emailHint': 'A plain-language copy, sent to you.',
  'parent.reports.send': 'Send this report',
  'parent.reports.noneTitle': 'No reports shared yet',
};

/* ----------------------------------------------------------------------------
   Hindi — covers auth, the role landing, settings, and the parent briefing/
   report. Any key NOT present here falls back to English at runtime (t()).
   Subject names are never translated (they are not in this map by design).
   ---------------------------------------------------------------------------- */
const hi: Dictionary = {
  'common.continue': 'जारी रखें',
  'common.back': 'वापस',
  'common.skipForNow': 'अभी छोड़ें',
  'common.signIn': 'साइन इन करें',
  'common.createAccount': 'खाता बनाएँ',
  'common.on': 'चालू',
  'common.off': 'बंद',

  'auth.role.title': 'आप यहाँ किस रूप में हैं',
  'auth.role.sub': 'Classess आपके अनुसार ढल जाता है। आप इसे बाद में बदल सकते हैं।',
  'auth.role.legend': 'अपनी भूमिका चुनें',
  'auth.identifier.titleSignUp': 'आपका ईमेल क्या है',
  'auth.identifier.titleSignIn': 'वापसी पर स्वागत है',
  'auth.identifier.subPhone': 'हम आपको साइन-इन कोड भेजेंगे।',
  'auth.identifier.subSignUp': 'इसी से आप साइन इन करेंगे।',
  'auth.identifier.subSignIn': 'जहाँ छोड़ा था वहीं से जारी रखने के लिए साइन इन करें।',
  'auth.email.label': 'ईमेल',
  'auth.phone.label': 'फ़ोन नंबर',
  'auth.secret.titlePhone': 'अपना कोड दर्ज करें',
  'auth.secret.titleSignUp': 'एक पासवर्ड चुनें',
  'auth.secret.titleSignIn': 'आपका पासवर्ड',
  'auth.secret.subSignUp': 'कम से कम छह अक्षर।',
  'auth.password.label': 'पासवर्ड',
  'auth.password.show': 'दिखाएँ',
  'auth.password.hide': 'छिपाएँ',
  'auth.forgot': 'पासवर्ड भूल गए',
  'auth.cta.createAccount': 'खाता बनाएँ',
  'auth.cta.verify': 'सत्यापित करें और जारी रखें',
  'auth.switch.haveAccount': 'क्या आपके पास पहले से खाता है?',
  'auth.switch.newHere': 'Classess पर नए हैं?',
  'auth.demoNote':
    'डेमो मोड में चल रहा है — आपका सत्र इसी डिवाइस पर स्थानीय रूप से रहता है, कोई व्यक्तिगत विवरण संग्रहीत नहीं होता।',
  'auth.forgot.title': 'अपना पासवर्ड रीसेट करें',
  'auth.forgot.sub': 'अपना ईमेल दर्ज करें और हम नया पासवर्ड सेट करने का लिंक भेजेंगे।',
  'auth.forgot.send': 'रीसेट लिंक भेजें',
  'auth.forgot.sent':
    'यदि उस ईमेल के लिए कोई खाता मौजूद है, तो रीसेट लिंक भेजा जा रहा है। आप इसे बंद कर अपना इनबॉक्स देख सकते हैं।',
  'auth.forgot.backToSignIn': 'साइन इन पर वापस जाएँ',
  'auth.reset.title': 'नया पासवर्ड सेट करें',
  'auth.reset.sub': 'अपना खाता रीसेट पूरा करने के लिए नया पासवर्ड चुनें।',
  'auth.reset.newLabel': 'नया पासवर्ड',
  'auth.reset.set': 'नया पासवर्ड सेट करें',
  'auth.reset.done': 'आपका पासवर्ड सेट हो गया है। अब आप इससे साइन इन कर सकते हैं।',
  'auth.reset.goSignIn': 'साइन इन पर जाएँ',

  'personalise.title': 'अपनी जगह को आकार देने का एक पल',
  'personalise.sub':
    'कुछ सहज टैप, कोई फ़ॉर्म नहीं। आप इनमें से कुछ भी बाद में सेटिंग्स में बदल सकते हैं।',
  'personalise.intent': 'आज आप किस लिए आए हैं',
  'personalise.subject': 'एक दिलचस्प विषय चुनें',
  'personalise.goal': 'आप इससे क्या पाना चाहेंगे',
  'personalise.language': 'कौन सी भाषा सबसे सहज लगती है',
  'personalise.footnote':
    'हर टैप एक संकेत है, फ़ॉर्म नहीं। मैं इन्हीं से आपकी जगह बनाता हूँ — आपको खुद को बताने की कभी ज़रूरत नहीं।',

  'landing.homeSuffix': 'होम',
  'landing.tryWithVidya': 'Vidya के साथ आज़माएँ',
  'landing.yourBriefing': 'आपका सारांश',
  'landing.quickLinks': 'त्वरित लिंक',
  'landing.offline':
    'आप ऑफ़लाइन हैं। मुख्य प्रवाह अब भी काम करते हैं; दोबारा जुड़ने पर नई बातचीत समन्वयित हो जाएगी।',

  'settings.eyebrow': 'आपकी प्राथमिकताएँ',
  'settings.title': 'सेटिंग्स',
  'settings.howVidya': 'Vidya कैसे मदद करता है और क्या पढ़ सकता है',
  'settings.language': 'भाषा',
  'settings.languageHelp':
    'वह भाषा चुनें जिसमें Classess आपको पढ़कर बताए। विषयों के नाम हर भाषा में एक जैसे रहते हैं।',
  'settings.behaviouralNote':
    'व्यवहार-संबंधी डेटा एक अनाम पहचान से जुड़ा है, आपके नाम से नहीं। क्या साझा हो यह आप तय करते हैं, और कभी भी बदल सकते हैं।',
  'settings.learned': 'मैंने आपके काम करने के तरीके के बारे में क्या सीखा',
  'settings.account': 'खाता',
  'settings.reonboard': 'ऑनबोर्डिंग फिर से चलाएँ',
  'settings.signOut': 'साइन आउट करें',

  'parent.reports.eyebrow': 'रिपोर्ट',
  'parent.reports.whose': 'किसकी रिपोर्ट',
  'parent.reports.sharedWithYou': 'आपके साथ साझा',
  'parent.reports.plainNote':
    'हर रिपोर्ट आपके लिए सरल भाषा में लिखी गई है। कोई कच्चे अंक नहीं — बस क्या अच्छा चल रहा है और कौन सा एक अगला कदम मदद करता है।',
  'parent.reports.releasedNote':
    'रिपोर्ट आपको एक शिक्षक द्वारा जारी की जाती है — कभी स्वतः नहीं। आप वही देखते हैं जो स्कूल ने साझा करना चुना है।',
  'parent.reports.celebrate': 'जश्न मनाएँ',
  'parent.reports.nextStep': 'अगला कदम',
  'parent.reports.sharedBy': 'द्वारा साझा',
  'parent.reports.email': 'यह रिपोर्ट ईमेल करें',
  'parent.reports.emailHint': 'एक सरल-भाषा प्रति, आपको भेजी गई।',
  'parent.reports.send': 'यह रिपोर्ट भेजें',
  'parent.reports.noneTitle': 'अभी तक कोई रिपोर्ट साझा नहीं की गई',
};

/** The full registry. English is the source + fallback; others are partial. */
export const DICTIONARIES: Record<Locale, Dictionary> = { en, hi };

/** The English source — exported so t() can fall back per key. */
export const SOURCE_DICTIONARY = en;
