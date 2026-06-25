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

  // Welcome preamble (the very first screen, before sign-in)
  'welcome.title': 'A calmer way to learn, teach, and run a school',
  'welcome.lede':
    'I am Vidya. I will be with you the whole way — learning what helps as we go, never asking you to fill in a form.',
  'welcome.beatsLabel': 'What happens next',
  'welcome.beat.signIn': 'Sign in — a code to your phone, or email. Nothing more than we need.',
  'welcome.beat.role': 'Tell me who you are here as — a student, a teacher, an admin, or a parent.',
  'welcome.beat.shape': 'A couple of natural taps, and your space takes shape around you.',
  'welcome.begin': 'Begin',
  'welcome.haveAccount': 'Already have an account?',
  'welcome.foot': 'There is nothing to fill in here, and nothing is final. You can change any of it later.',

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
  // Vidya's docked narration through the personalise step.
  'personalise.vidya.greet':
    'I am Vidya. Let us shape a calm space that fits you. A couple of natural taps, and I learn as we go — never a form.',
  'personalise.vidya.choosing':
    'Good. Each tap is a gentle hint. I will widen things out as we learn what helps.',
  // The DPDP age-tier + consent step (transparent, revocable, tier-bounded).
  'personalise.consent.heading': 'Your age, so I stay within the law',
  'personalise.consent.agree.adult': 'Personalise for me',
  'personalise.consent.agree.child': 'A guardian agrees',
  'personalise.consent.notNow': 'Not now',
  'personalise.consent.revocable':
    'You can review or revoke this any time in Settings. Nothing here is final or hidden.',

  // Role landing
  'landing.homeSuffix': 'home',
  'landing.sub': 'Ask anything, or pick up where you left off',
  'landing.askPlaceholder': 'Ask Vidya, or describe what you want to do',
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

  // Parent · This week (/parent)
  'parent.week.eyebrow': 'This week',
  'parent.week.title': 'Welcome. Here is a calm look at this week.',
  'parent.week.dockIntro':
    'This is a calm view for your family. Ask how a child is doing, what to support at home, or to see a recent win.',
  'parent.week.chip1': 'How is my child this week',
  'parent.week.chip2': 'What needs attention',
  'parent.week.chip3': 'Show a recent win',
  'parent.week.whose': 'Whose week are we looking at',
  'parent.week.three': 'Three things this week',
  'parent.week.threeNote':
    'A short, honest list for {child}. Nothing here is urgent or alarming — it is where a little attention helps most.',
  'parent.week.next': 'Where to go next',
  'parent.week.linkChild': 'The child view',
  'parent.week.linkChildSub': 'Progress, strengths and support areas',
  'parent.week.linkReports': 'Reports and feedback',
  'parent.week.linkReportsSub': 'Celebration points and next steps',
  'parent.week.linkTogether': 'Learn alongside and PTM',
  'parent.week.linkTogetherSub': 'Activities for home and meeting prep',
  'parent.week.partnership':
    'You see only what {child}’s school has chosen to share with you. This is a partnership, not a watch list.',
  'parent.week.open': 'Open',
  'parent.week.acting': 'Setting this up…',
  'parent.week.setAside': 'Set aside',
  'parent.week.bringBack': 'Bring back',
  'parent.week.actionTaken': 'Done',
  'parent.week.actionTakenSupport': 'Routed to a tracked plan — owned and followed up, not lost.',
  'parent.week.actionTakenNoted': 'Noted on your record. Nicely done.',

  // Parent · The child view (/parent/child)
  'parent.child.eyebrow': 'The child view',
  'parent.child.title': 'The child view',
  'parent.child.titleChild': 'How {child} is doing',
  'parent.child.dockIntro':
    'Ask about a strength, a place to support, or how a topic has grown over time.',
  'parent.child.chip1': 'What is going well',
  'parent.child.chip2': 'Where can I help',
  'parent.child.chip3': 'What changed this month',
  'parent.child.choose': 'Choose a child',
  'parent.child.proud': 'A moment to be proud of',
  'parent.child.timeline': 'This child’s timeline',
  'parent.child.goingWell': 'What is going well',
  'parent.child.noStrengths': 'More strengths will appear here as the term unfolds.',
  'parent.child.support': 'Where a little support helps',
  'parent.child.supportNote':
    'These are not problems — they are the next small steps. Every one comes with something you can do together.',
  'parent.child.noSupport': 'Nothing needs extra support right now.',
  'parent.child.note':
    'Everything here is in plain language and drawn from {child}’s own work, shared with you by the school. You see only what consent permits.',
  'parent.child.independent': 'Now independent',
  'parent.child.goingWellTag': 'Going well',
  'parent.child.nextStepTag': 'Next step',

  // Parent · Learn alongside & PTM (/parent/together)
  'parent.together.eyebrow': 'Together',
  'parent.together.title': 'Learn alongside and PTM',
  'parent.together.titleChild': 'Learning alongside {child}',
  'parent.together.dockIntro':
    'Ask for a short activity to do together, or help preparing for the parent-teacher meeting.',
  'parent.together.chip1': 'A 10-minute activity',
  'parent.together.chip2': 'Help me prepare for the meeting',
  'parent.together.chip3': 'What to ask the teacher',
  'parent.together.choose': 'Choose a child',
  'parent.together.atHome': 'Do this together at home',
  'parent.together.atHomeNote':
    'Short, warm activities — each tied to where {child} is growing right now. No pressure, just time together.',
  'parent.together.noActivities': 'New activities will appear here as topics move on.',
  'parent.together.about': 'About {minutes} min',
  'parent.together.togetherLabel': 'Together.',
  'parent.together.whyHelps': 'Why it helps.',
  'parent.together.ptm': 'Parent-teacher meeting',
  'parent.together.ptmNone': 'No meeting scheduled yet',
  'parent.together.ptmNoneNote':
    'There is nothing urgent for {child}. You can request a meeting with the teacher whenever it suits you, and a prep list will be ready here.',
  'parent.together.ptmRequest': 'Request a meeting',
  'parent.together.ptmRequesting': 'Requesting…',
  'parent.together.ptmRequested': 'Request sent',
  'parent.together.ptmRequestedNote':
    'The teacher will propose a time. You will see it here, and a prep list will be ready.',
  'parent.together.ptmScheduled': 'Scheduled',
  'parent.together.ptmBring': 'Bring these to the meeting',
  'parent.together.ptmCalendar': 'Add to your calendar',
  'parent.together.ptmReschedule': 'Reschedule',
  'parent.together.ptmRescheduleNote':
    'A reschedule request has been sent. The teacher will propose a new time and it will appear here.',
  'parent.together.note':
    'These suggestions come from {child}’s shared learning. You decide what to do and when — nothing is set for you.',
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

  'welcome.title': 'सीखने, पढ़ाने और स्कूल चलाने का एक शांत तरीका',
  'welcome.lede':
    'मैं Vidya हूँ। मैं पूरे रास्ते आपके साथ रहूँगी — चलते-चलते सीखती हूँ कि क्या मदद करता है, कभी कोई फ़ॉर्म भरने को नहीं कहती।',
  'welcome.beatsLabel': 'आगे क्या होगा',
  'welcome.beat.signIn': 'साइन इन करें — आपके फ़ोन पर एक कोड, या ईमेल से। ज़रूरत से ज़्यादा कुछ नहीं।',
  'welcome.beat.role': 'बताएँ कि आप यहाँ किस रूप में हैं — छात्र, शिक्षक, व्यवस्थापक, या अभिभावक।',
  'welcome.beat.shape': 'कुछ सहज टैप, और आपकी जगह आपके अनुसार आकार लेती है।',
  'welcome.begin': 'शुरू करें',
  'welcome.haveAccount': 'क्या आपके पास पहले से खाता है?',
  'welcome.foot': 'यहाँ कुछ भरने को नहीं है, और कुछ भी अंतिम नहीं है। आप इसे बाद में बदल सकते हैं।',

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
  'personalise.vidya.greet':
    'मैं Vidya हूँ। आइए आपके लिए एक शांत जगह बनाएँ। कुछ सहज टैप, और मैं चलते-चलते सीखती रहूँगी — कभी कोई फ़ॉर्म नहीं।',
  'personalise.vidya.choosing':
    'अच्छा। हर टैप एक हल्का संकेत है। जैसे-जैसे हमें समझ आएगा, मैं चीज़ें और खोलती जाऊँगी।',
  'personalise.consent.heading': 'आपकी उम्र, ताकि मैं कानून के भीतर रहूँ',
  'personalise.consent.agree.adult': 'मेरे लिए वैयक्तिकृत करें',
  'personalise.consent.agree.child': 'एक अभिभावक सहमत हैं',
  'personalise.consent.notNow': 'अभी नहीं',
  'personalise.consent.revocable':
    'आप इसे कभी भी सेटिंग्स में देख या वापस ले सकते हैं। यहाँ कुछ भी अंतिम या छिपा हुआ नहीं है।',

  'landing.homeSuffix': 'होम',
  'landing.sub': 'कुछ भी पूछें, या जहाँ छोड़ा था वहीं से शुरू करें',
  'landing.askPlaceholder': 'Vidya से पूछें, या बताएँ कि आप क्या करना चाहते हैं',
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

  // Parent · This week (/parent)
  'parent.week.eyebrow': 'इस सप्ताह',
  'parent.week.title': 'स्वागत है। इस सप्ताह की एक शांत झलक यहाँ है।',
  'parent.week.dockIntro':
    'यह आपके परिवार के लिए एक शांत दृश्य है। पूछें कि बच्चा कैसा कर रहा है, घर पर किसमें सहायता करें, या एक हालिया उपलब्धि देखें।',
  'parent.week.chip1': 'इस सप्ताह मेरा बच्चा कैसा है',
  'parent.week.chip2': 'किस पर ध्यान चाहिए',
  'parent.week.chip3': 'एक हालिया उपलब्धि दिखाएँ',
  'parent.week.whose': 'हम किसका सप्ताह देख रहे हैं',
  'parent.week.three': 'इस सप्ताह तीन बातें',
  'parent.week.threeNote':
    '{child} के लिए एक छोटी, ईमानदार सूची। यहाँ कुछ भी अत्यावश्यक या चिंताजनक नहीं है — यह वहाँ है जहाँ थोड़ा ध्यान सबसे अधिक मदद करता है।',
  'parent.week.next': 'आगे कहाँ जाएँ',
  'parent.week.linkChild': 'बच्चे का दृश्य',
  'parent.week.linkChildSub': 'प्रगति, ताकतें और सहायता के क्षेत्र',
  'parent.week.linkReports': 'रिपोर्ट और प्रतिक्रिया',
  'parent.week.linkReportsSub': 'जश्न के बिंदु और अगले कदम',
  'parent.week.linkTogether': 'साथ सीखें और अभिभावक-शिक्षक बैठक',
  'parent.week.linkTogetherSub': 'घर के लिए गतिविधियाँ और बैठक की तैयारी',
  'parent.week.partnership':
    'आप केवल वही देखते हैं जो {child} के स्कूल ने आपके साथ साझा करना चुना है। यह एक साझेदारी है, निगरानी सूची नहीं।',
  'parent.week.open': 'खोलें',
  'parent.week.acting': 'यह तैयार किया जा रहा है…',
  'parent.week.setAside': 'अलग रखें',
  'parent.week.bringBack': 'वापस लाएँ',
  'parent.week.actionTaken': 'हो गया',
  'parent.week.actionTakenSupport': 'एक ट्रैक की गई योजना में भेजा गया — स्वामित्व सहित और अनुसरण किया गया, खोया नहीं।',
  'parent.week.actionTakenNoted': 'आपके रिकॉर्ड में दर्ज। बढ़िया किया।',

  // Parent · The child view (/parent/child)
  'parent.child.eyebrow': 'बच्चे का दृश्य',
  'parent.child.title': 'बच्चे का दृश्य',
  'parent.child.titleChild': '{child} कैसा कर रहा है',
  'parent.child.dockIntro':
    'किसी ताकत के बारे में, सहायता की किसी जगह के बारे में, या समय के साथ कोई विषय कैसे बढ़ा है, इसके बारे में पूछें।',
  'parent.child.chip1': 'क्या अच्छा चल रहा है',
  'parent.child.chip2': 'मैं कहाँ मदद कर सकता हूँ',
  'parent.child.chip3': 'इस महीने क्या बदला',
  'parent.child.choose': 'एक बच्चा चुनें',
  'parent.child.proud': 'गर्व करने योग्य एक पल',
  'parent.child.timeline': 'इस बच्चे की समयरेखा',
  'parent.child.goingWell': 'क्या अच्छा चल रहा है',
  'parent.child.noStrengths': 'जैसे-जैसे सत्र आगे बढ़ेगा, और ताकतें यहाँ दिखाई देंगी।',
  'parent.child.support': 'जहाँ थोड़ी सहायता मदद करती है',
  'parent.child.supportNote':
    'ये समस्याएँ नहीं हैं — ये अगले छोटे कदम हैं। हर एक के साथ कुछ ऐसा आता है जो आप साथ मिलकर कर सकते हैं।',
  'parent.child.noSupport': 'अभी किसी अतिरिक्त सहायता की आवश्यकता नहीं है।',
  'parent.child.note':
    'यहाँ सब कुछ सरल भाषा में है और {child} के अपने काम से लिया गया है, जिसे स्कूल ने आपके साथ साझा किया है। आप केवल वही देखते हैं जिसकी सहमति अनुमति देती है।',
  'parent.child.independent': 'अब स्वतंत्र',
  'parent.child.goingWellTag': 'अच्छा चल रहा है',
  'parent.child.nextStepTag': 'अगला कदम',

  // Parent · Learn alongside & PTM (/parent/together)
  'parent.together.eyebrow': 'साथ में',
  'parent.together.title': 'साथ सीखें और अभिभावक-शिक्षक बैठक',
  'parent.together.titleChild': '{child} के साथ सीखना',
  'parent.together.dockIntro':
    'साथ करने के लिए एक छोटी गतिविधि माँगें, या अभिभावक-शिक्षक बैठक की तैयारी में मदद लें।',
  'parent.together.chip1': 'एक 10-मिनट की गतिविधि',
  'parent.together.chip2': 'बैठक की तैयारी में मेरी मदद करें',
  'parent.together.chip3': 'शिक्षक से क्या पूछें',
  'parent.together.choose': 'एक बच्चा चुनें',
  'parent.together.atHome': 'घर पर यह साथ करें',
  'parent.together.atHomeNote':
    'छोटी, गर्मजोशी भरी गतिविधियाँ — हर एक उससे जुड़ी जहाँ {child} अभी बढ़ रहा है। कोई दबाव नहीं, बस साथ बिताया समय।',
  'parent.together.noActivities': 'जैसे-जैसे विषय आगे बढ़ेंगे, यहाँ नई गतिविधियाँ दिखाई देंगी।',
  'parent.together.about': 'लगभग {minutes} मिनट',
  'parent.together.togetherLabel': 'साथ में।',
  'parent.together.whyHelps': 'यह क्यों मदद करता है।',
  'parent.together.ptm': 'अभिभावक-शिक्षक बैठक',
  'parent.together.ptmNone': 'अभी कोई बैठक निर्धारित नहीं',
  'parent.together.ptmNoneNote':
    '{child} के लिए कुछ भी अत्यावश्यक नहीं है। आप जब चाहें शिक्षक के साथ बैठक का अनुरोध कर सकते हैं, और यहाँ एक तैयारी सूची तैयार रहेगी।',
  'parent.together.ptmRequest': 'बैठक का अनुरोध करें',
  'parent.together.ptmRequesting': 'अनुरोध किया जा रहा है…',
  'parent.together.ptmRequested': 'अनुरोध भेजा गया',
  'parent.together.ptmRequestedNote':
    'शिक्षक एक समय प्रस्तावित करेंगे। आप इसे यहाँ देखेंगे, और एक तैयारी सूची तैयार रहेगी।',
  'parent.together.ptmScheduled': 'निर्धारित',
  'parent.together.ptmBring': 'इन्हें बैठक में लाएँ',
  'parent.together.ptmCalendar': 'अपने कैलेंडर में जोड़ें',
  'parent.together.ptmReschedule': 'पुनर्निर्धारित करें',
  'parent.together.ptmRescheduleNote':
    'पुनर्निर्धारण अनुरोध भेज दिया गया है। शिक्षक एक नया समय प्रस्तावित करेंगे और यह यहाँ दिखाई देगा।',
  'parent.together.note':
    'ये सुझाव {child} के साझा किए गए सीखने से आते हैं। आप तय करते हैं कि क्या करना है और कब — कुछ भी आपके लिए तय नहीं किया जाता।',
};

/** The full registry. English is the source + fallback; others are partial. */
export const DICTIONARIES: Record<Locale, Dictionary> = { en, hi };

/** The English source — exported so t() can fall back per key. */
export const SOURCE_DICTIONARY = en;
