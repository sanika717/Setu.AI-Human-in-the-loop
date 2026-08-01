/* ============================================================================
 * app-ui.js — SAHAAY.AI frontend UX layer (dashboard, sidebar, multi-page
 * navigation, language switch, security confirmation modal, chat UI extras).
 *
 * IMPORTANT: this file is purely additive. It never redefines, removes, or
 * duplicates anything app.js already does — it only reads app.js's DOM
 * (element IDs, form submissions, the confirm() dialog) and layers
 * presentation/navigation on top. Every backend call in this project still
 * happens exactly where it always did, in app.js. Load order in index.html
 * is app.js then app-ui.js, so everything app.js wires up already exists by
 * the time this file runs.
 * ==========================================================================*/

(function () {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* i18n — UI chrome only (nav, headings, buttons, static copy).        */
  /* Sahaay.AI's own multilingual reasoning (the chat) is handled server-*/
  /* side by intent_service, which today supports en/hi/mr/bn/ta/te.     */
  /* Kannada (kn) is included here per the branding requirement, but      */
  /* intent_service does not have a Kannada keyword taxonomy yet — chat   */
  /* messages typed in Kannada fall back to English detection server-side */
  /* and a one-time notice explains that. This is a real, disclosed gap,  */
  /* not a silent one.                                                    */
  /* ------------------------------------------------------------------ */

  const SUPPORTED_CHAT_LANGUAGES = new Set(["en", "hi", "mr", "bn", "ta", "te"]);

  const I18N = {
    en: {
      tagline: "Secure AI Banking Assistant",
      "nav.dashboard": "Dashboard", "nav.chat": "Chat", "nav.upload": "Upload",
      "nav.applications": "Applications", "nav.validate": "Validation", "nav.extract": "AI Extraction",
      "nav.review": "Human Review", "nav.portal": "Official Portal", "nav.status": "Application Status",
      "nav.settings": "Settings", "nav.support": "Support Dashboard",
      "sidebar.footer": "Every action here is logged, reversible, and reviewed by a human before anything is submitted.",
      "pageTitle.dashboard": "Dashboard", "pageSubtitle.dashboard": "Welcome back — here's where you left off.",
      "pageTitle.support": "Support Dashboard", "pageSubtitle.support": "Pending human-assistance requests and live sessions (demo).",
      "pageTitle.chat": "Chat", "pageSubtitle.chat": "Ask Sahaay.AI in your own words.",
      "pageTitle.upload": "Document Upload", "pageSubtitle.upload": "Hash and store a document securely.",
      "pageTitle.validate": "Document Validation", "pageSubtitle.validate": "Check documents against the official catalog.",
      "pageTitle.extract": "AI Extraction", "pageSubtitle.extract": "Pull structured fields out of validated documents.",
      "pageTitle.review": "Human Review", "pageSubtitle.review": "Approve, reject, or edit each extracted field.",
      "pageTitle.portal": "Official Portal Guidance", "pageSubtitle.portal": "Redirects, security-checked every time.",
      "pageTitle.status": "Application Status", "pageSubtitle.status": "Look up any application by ID.",
      "pageTitle.settings": "Settings", "pageSubtitle.settings": "Language and interface preferences.",
      "dashboard.greeting": "Hello! What would you like to do today?",
      "dashboard.greetingSub": "Ask me in your own words, or use the shortcuts below — I'll guide you the rest of the way.",
      "dashboard.chatPlaceholder": "e.g. I want to apply for an old age pension",
      "dashboard.chatSend": "Ask Sahaay.AI",
      "dashboard.continue": "Continue Application", "dashboard.continueDesc": "Pick up your most recent application where you left off.",
      "dashboard.track": "Track Application", "dashboard.trackDesc": "Check the status, audit log, and reports for any application.",
      "dashboard.newApp": "Start a New Request", "dashboard.newAppDesc": "Upload a document or ask Sahaay.AI to begin.",
      "dashboard.recent": "Recent Applications",
      "dashboard.recentEmpty": "No applications yet — start a conversation or load one by ID from Application Status.",
      "chat.intro": "Describe what you need in your own words — e.g. \"I want to apply for an old age pension\" — and Sahaay.AI will work out the right official service, ask any follow-up questions it needs, and hand you off to the guided portal once it knows enough.",
      "chat.placeholder": "Say hello, or describe what you need help with, to get started.",
      "chat.inputPlaceholder": "Type your message...", "chat.send": "Send", "chat.startOver": "Start Over",
      "upload.intro": "Select a file, review its SHA-256 hash, and store it securely. Text files can then be pulled straight into Validation and Extraction with their \"Use last upload\" button — no copy/paste needed. Scanned or image documents still need their text pasted in manually until an OCR provider is connected.",
      "upload.titleLabel": "Title", "upload.sourceLabel": "Source", "upload.fileLabel": "File",
      "upload.hashLabel": "Computed hash:", "upload.noFile": "No file selected", "upload.submit": "Upload Document",
      "validate.intro": "Validate applicant documents against Sahaay.AI's document catalog before they are sent for AI extraction.",
      "validate.loadingRef": "Loading supported document types & official services...",
      "validate.applicantId": "Applicant ID", "validate.service": "Service", "validate.serviceOptional": "-- Select a service (optional) --",
      "validate.applicantAge": "Applicant Age", "validate.addDoc": "+ Add Document", "validate.submit": "Validate Documents",
      "extract.intro": "Send validated documents to the AI Guidance Engine and review each extracted field with its confidence and source.",
      "extract.applicantId": "Applicant ID", "extract.addDoc": "+ Add Document", "extract.submit": "Run Extraction",
      "review.intro": "Send an extraction result to the Trust & Governance Engine, then approve, reject, or edit each field as a caseworker. Once every field has a decision, verify an OTP (and any Trusted Delegate approval) and submit the application — every action is written to an immutable audit log.",
      "review.actorLabel": "Caseworker ID (used as \"actor\" on every decision below)",
      "review.sendExtraction": "Send last extraction to Governance", "review.loadExisting": "Or load an existing application",
      "review.load": "Load", "review.applicationLabel": "Application", "review.refresh": "Refresh",
      "review.otpHeading": "OTP & Submission", "review.otpDest": "OTP destination (phone/e-mail)", "review.otpCode": "OTP code",
      "review.requestOtp": "Request OTP", "review.verifyOtp": "Verify OTP", "review.checkReadiness": "Check Submission Readiness",
      "review.submitApp": "Submit Application", "review.auditHeading": "Audit Log & Reports",
      "review.loadAudit": "Load Audit Log", "review.verifyChain": "Verify Audit Chain", "review.downloadReport": "Download Report",
      "review.delegateHeading": "Trusted Delegate (Human-in-the-Loop)",
      "review.delegateHint": "A Trusted Delegate (family member, caregiver, or NGO volunteer) can be asked to approve this application before it is submitted. When \"approval required\" is checked, submission stays blocked until they approve.",
      "review.delegateName": "Delegate name", "review.delegateRelationship": "Relationship", "review.delegateContact": "Contact",
      "review.delegateApprovalRequired": "Approval required before submission", "review.delegateRegisteredBy": "Registered by",
      "review.delegateRegister": "Register Delegate", "review.delegateLoad": "Load Current Delegate",
      "review.delegateApprove": "Approve (as delegate)", "review.delegateRevoke": "Revoke Delegate",
      "portal.intro": "This guide acts as a layer above government banking portals and asks for your permission before every redirect. Sahaay.AI's Security Shield checks every redirect first — if something doesn't check out, the redirect is paused and shown below instead of opening.",
      "portal.assistantNote": "Sahaay.AI stays with you here — after you confirm, you'll get a security check, a plain-language explanation of what happens next, and only then the official site opens in a new tab.",
      "portal.noteLabel": "Permission note", "portal.apiKeyLabel": "Portal API key",
      "status.intro": "Look up any application by ID to see its current stage at a glance, then jump into Human Review for the full detail — field decisions, OTP, delegate approval, audit log, and reports.",
      "status.idLabel": "Application ID", "status.lookup": "Look Up",
      "settings.language": "Language", "settings.languageDesc": "Choose the language for the Sahaay.AI interface and chat. This can also be changed anytime from the header.",
      "settings.about": "About this build",
      "settings.aboutDesc": "Sahaay.AI never replaces an official website, never stores passwords/OTPs/PINs, and keeps a human in control at every sensitive step. Every backend call below points at the same independent microservices as before — this update only reorganizes the interface around them.",
      "step.upload": "Upload", "step.validate": "Validation", "step.extract": "Extraction",
      "step.review": "Human Review", "step.portal": "Official Portal", "step.completed": "Completed",
      "securityModal.title": "Confirm official redirect", "securityModal.cancel": "Cancel", "securityModal.continue": "Continue",
      "chat.kannadaNotice": "Kannada chat support is coming soon — Sahaay.AI will detect your message in English for now. The interface stays in Kannada.",
      "takeControl.toggle": "Take Control", "takeControl.heading": "Take Control Mode",
      "takeControl.exit": "Exit", "takeControl.on": "Take Control is on — Sahaay.AI will stay beside you and explain each step. Exit any time.",
      "takeControl.dashboard": "I'll stay with you across the whole application. Start by telling me what you need, or upload a document.",
      "takeControl.chat": "Tell me what you're trying to do in your own words — I'll figure out the right official service and ask only what's needed.",
      "takeControl.upload": "Choose the document you were asked for. I'll compute a secure hash and keep it ready for validation and extraction.",
      "takeControl.validate": "I'm checking this document against the official catalog for the service you picked, and flagging anything missing.",
      "takeControl.extract": "I'm reading the fields out of your document. Review each one below — nothing is final until a human approves it.",
      "takeControl.review": "This is where a human checks every field. If anything sensitive shows up, I'll ask your permission before going further.",
      "takeControl.portal": "When you're ready, I'll verify the official site is genuine and secure, explain what happens next, and stay visible while you fill the form.",
      "takeControl.status": "Look up any application here to see exactly which stage it's at.",
      "govGate.heading": "Sensitive information detected",
      "govGate.question": "Would you like AI to process this information?",
      "govGate.encryption": "🔐 Encrypted in transit and at rest",
      "govGate.audit": "📜 Every action is written to the immutable audit log",
      "govGate.permission": "✅ Nothing proceeds without your explicit permission",
      "govGate.decline": "Not now", "govGate.accept": "Yes, proceed",
      "govGate.declinedNotice": "No problem — nothing has been processed. Come back to this page any time to say yes.",
    },
    hi: {
      tagline: "सुरक्षित एआई बैंकिंग सहायक",
      "nav.dashboard": "डैशबोर्ड", "nav.chat": "चैट", "nav.upload": "अपलोड",
      "nav.applications": "आवेदन", "nav.validate": "सत्यापन", "nav.extract": "एआई निष्कर्षण",
      "nav.review": "मानव समीक्षा", "nav.portal": "आधिकारिक पोर्टल", "nav.status": "आवेदन स्थिति",
      "nav.settings": "सेटिंग्स",
      "dashboard.greeting": "नमस्ते! आज आप क्या करना चाहेंगे?",
      "dashboard.greetingSub": "अपने शब्दों में पूछें, या नीचे दिए शॉर्टकट का उपयोग करें — मैं आपका मार्गदर्शन करूँगा।",
      "dashboard.chatPlaceholder": "जैसे, मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है",
      "dashboard.chatSend": "सहाय.एआई से पूछें",
      "dashboard.continue": "आवेदन जारी रखें", "dashboard.track": "आवेदन ट्रैक करें", "dashboard.newApp": "नया अनुरोध शुरू करें",
      "dashboard.recent": "हाल के आवेदन",
      "chat.placeholder": "नमस्ते कहें, या शुरू करने के लिए आपको किस मदद की ज़रूरत है बताएं।",
      "chat.inputPlaceholder": "अपना संदेश लिखें...", "chat.send": "भेजें", "chat.startOver": "फिर से शुरू करें",
      "step.upload": "अपलोड", "step.validate": "सत्यापन", "step.extract": "निष्कर्षण",
      "step.review": "मानव समीक्षा", "step.portal": "आधिकारिक पोर्टल", "step.completed": "पूर्ण",
      "securityModal.title": "आधिकारिक रीडायरेक्ट की पुष्टि करें", "securityModal.cancel": "रद्द करें", "securityModal.continue": "जारी रखें",
      "takeControl.toggle": "टेक कंट्रोल", "takeControl.heading": "टेक कंट्रोल मोड",
      "takeControl.exit": "बाहर निकलें",
      "takeControl.dashboard": "मैं पूरे आवेदन के दौरान आपके साथ रहूँगा। बताइए आपको क्या चाहिए, या कोई दस्तावेज़ अपलोड करें।",
      "takeControl.chat": "अपने शब्दों में बताएं आप क्या करना चाहते हैं — मैं सही आधिकारिक सेवा पहचान लूँगा।",
      "takeControl.upload": "वह दस्तावेज़ चुनें जो माँगा गया था। मैं सुरक्षित हैश बनाकर उसे तैयार रखूँगा।",
      "takeControl.validate": "मैं इस दस्तावेज़ को आधिकारिक सूची से जाँच रहा हूँ।",
      "takeControl.extract": "मैं आपके दस्तावेज़ से जानकारी निकाल रहा हूँ। हर एक की समीक्षा करें।",
      "takeControl.review": "यहाँ एक इंसान हर जानकारी जाँचता है। संवेदनशील जानकारी होने पर मैं पहले आपकी अनुमति माँगूँगा।",
      "takeControl.portal": "जब आप तैयार हों, मैं आधिकारिक साइट की सुरक्षा जाँचूँगा और फ़ॉर्म भरते समय साथ रहूँगा।",
      "takeControl.status": "किसी भी आवेदन की स्थिति यहाँ देखें।",
      "govGate.heading": "संवेदनशील जानकारी मिली", "govGate.question": "क्या आप चाहते हैं कि एआई इस जानकारी को प्रोसेस करे?",
      "govGate.encryption": "🔐 ट्रांज़िट और स्टोरेज में एन्क्रिप्टेड", "govGate.audit": "📜 हर कार्रवाई ऑडिट लॉग में दर्ज",
      "govGate.permission": "✅ आपकी अनुमति के बिना कुछ भी आगे नहीं बढ़ेगा",
      "govGate.decline": "अभी नहीं", "govGate.accept": "हाँ, आगे बढ़ें",
      "govGate.declinedNotice": "कोई बात नहीं — कुछ भी प्रोसेस नहीं हुआ। जब चाहें, यहाँ वापस आकर हाँ कहें।",
    },
    mr: {
      tagline: "सुरक्षित एआय बँकिंग सहाय्यक",
      "nav.dashboard": "डॅशबोर्ड", "nav.chat": "गप्पा", "nav.upload": "अपलोड",
      "nav.applications": "अर्ज", "nav.validate": "पडताळणी", "nav.extract": "एआय एक्सट्रॅक्शन",
      "nav.review": "मानवी पुनरावलोकन", "nav.portal": "अधिकृत पोर्टल", "nav.status": "अर्जाची स्थिती",
      "nav.settings": "सेटिंग्ज",
      "dashboard.greeting": "नमस्कार! आज तुम्हाला काय करायचे आहे?",
      "dashboard.greetingSub": "तुमच्या शब्दांत विचारा, किंवा खालील शॉर्टकट वापरा — मी तुम्हाला मार्गदर्शन करेन.",
      "dashboard.chatSend": "सहाय.एआयला विचारा",
      "dashboard.continue": "अर्ज सुरू ठेवा", "dashboard.track": "अर्ज ट्रॅक करा", "dashboard.newApp": "नवीन विनंती सुरू करा",
      "dashboard.recent": "अलीकडील अर्ज",
      "chat.inputPlaceholder": "तुमचा संदेश टाइप करा...", "chat.send": "पाठवा", "chat.startOver": "पुन्हा सुरू करा",
      "step.upload": "अपलोड", "step.validate": "पडताळणी", "step.extract": "एक्सट्रॅक्शन",
      "step.review": "मानवी पुनरावलोकन", "step.portal": "अधिकृत पोर्टल", "step.completed": "पूर्ण",
    },
    ta: {
      tagline: "பாதுகாப்பான AI வங்கி உதவியாளர்",
      "nav.dashboard": "டாஷ்போர்டு", "nav.chat": "அரட்டை", "nav.upload": "பதிவேற்று",
      "nav.applications": "விண்ணப்பங்கள்", "nav.validate": "சரிபார்ப்பு", "nav.extract": "AI பிரித்தெடுத்தல்",
      "nav.review": "மனித மதிப்பாய்வு", "nav.portal": "அதிகாரப்பூர்வ போர்டல்", "nav.status": "விண்ணப்ப நிலை",
      "nav.settings": "அமைப்புகள்",
      "dashboard.greeting": "வணக்கம்! இன்று நீங்கள் என்ன செய்ய விரும்புகிறீர்கள்?",
      "dashboard.chatSend": "சஹாய்.AI-யிடம் கேளுங்கள்",
      "dashboard.continue": "விண்ணப்பத்தைத் தொடரவும்", "dashboard.track": "விண்ணப்பத்தைக் கண்காணிக்கவும்", "dashboard.newApp": "புதிய கோரிக்கையைத் தொடங்கவும்",
      "dashboard.recent": "சமீபத்திய விண்ணப்பங்கள்",
      "chat.inputPlaceholder": "உங்கள் செய்தியை தட்டச்சு செய்யவும்...", "chat.send": "அனுப்பு", "chat.startOver": "மீண்டும் தொடங்கு",
      "step.upload": "பதிவேற்று", "step.validate": "சரிபார்ப்பு", "step.extract": "பிரித்தெடுத்தல்",
      "step.review": "மனித மதிப்பாய்வு", "step.portal": "அதிகாரப்பூர்வ போர்டல்", "step.completed": "முடிந்தது",
    },
    te: {
      tagline: "సురక్షిత AI బ్యాంకింగ్ సహాయకుడు",
      "nav.dashboard": "డాష్‌బోర్డ్", "nav.chat": "చాట్", "nav.upload": "అప్‌లోడ్",
      "nav.applications": "దరఖాస్తులు", "nav.validate": "ధృవీకరణ", "nav.extract": "AI వెలికితీత",
      "nav.review": "మానవ సమీక్ష", "nav.portal": "అధికారిక పోర్టల్", "nav.status": "దరఖాస్తు స్థితి",
      "nav.settings": "సెట్టింగ్‌లు",
      "dashboard.greeting": "నమస్కారం! ఈరోజు మీరు ఏమి చేయాలనుకుంటున్నారు?",
      "dashboard.chatSend": "సహాయ్.AI ని అడగండి",
      "dashboard.continue": "దరఖాస్తును కొనసాగించండి", "dashboard.track": "దరఖాస్తును ట్రాక్ చేయండి", "dashboard.newApp": "కొత్త అభ్యర్థన ప్రారంభించండి",
      "dashboard.recent": "ఇటీవలి దరఖాస్తులు",
      "chat.inputPlaceholder": "మీ సందేశాన్ని టైప్ చేయండి...", "chat.send": "పంపు", "chat.startOver": "మళ్లీ ప్రారంభించండి",
      "step.upload": "అప్‌లోడ్", "step.validate": "ధృవీకరణ", "step.extract": "వెలికితీత",
      "step.review": "మానవ సమీక్ష", "step.portal": "అధికారిక పోర్టల్", "step.completed": "పూర్తయింది",
    },
    kn: {
      tagline: "ಸುರಕ್ಷಿತ AI ಬ್ಯಾಂಕಿಂಗ್ ಸಹಾಯಕ",
      "nav.dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "nav.chat": "ಚಾಟ್", "nav.upload": "ಅಪ್‌ಲೋಡ್",
      "nav.applications": "ಅರ್ಜಿಗಳು", "nav.validate": "ಪರಿಶೀಲನೆ", "nav.extract": "AI ಹೊರತೆಗೆಯುವಿಕೆ",
      "nav.review": "ಮಾನವ ಪರಿಶೀಲನೆ", "nav.portal": "ಅಧಿಕೃತ ಪೋರ್ಟಲ್", "nav.status": "ಅರ್ಜಿ ಸ್ಥಿತಿ",
      "nav.settings": "ಸಂಯೋಜನೆಗಳು",
      "dashboard.greeting": "ನಮಸ್ಕಾರ! ಇಂದು ನೀವು ಏನು ಮಾಡಲು ಬಯಸುತ್ತೀರಿ?",
      "dashboard.chatSend": "ಸಹಾಯ.AI ಅನ್ನು ಕೇಳಿ",
      "dashboard.continue": "ಅರ್ಜಿ ಮುಂದುವರಿಸಿ", "dashboard.track": "ಅರ್ಜಿ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ", "dashboard.newApp": "ಹೊಸ ವಿನಂತಿ ಪ್ರಾರಂಭಿಸಿ",
      "dashboard.recent": "ಇತ್ತೀಚಿನ ಅರ್ಜಿಗಳು",
      "chat.inputPlaceholder": "ನಿಮ್ಮ ಸಂದೇಶ ಟೈಪ್ ಮಾಡಿ...", "chat.send": "ಕಳುಹಿಸಿ", "chat.startOver": "ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಿ",
      "step.upload": "ಅಪ್‌ಲೋಡ್", "step.validate": "ಪರಿಶೀಲನೆ", "step.extract": "ಹೊರತೆಗೆಯುವಿಕೆ",
      "step.review": "ಮಾನವ ಪರಿಶೀಲನೆ", "step.portal": "ಅಧಿಕೃತ ಪೋರ್ಟಲ್", "step.completed": "ಪೂರ್ಣಗೊಂಡಿದೆ",
    },
    bn: {
      tagline: "নিরাপদ এআই ব্যাংকিং সহায়ক",
      "nav.dashboard": "ড্যাশবোর্ড", "nav.chat": "চ্যাট", "nav.upload": "আপলোড",
      "nav.applications": "আবেদন", "nav.validate": "যাচাইকরণ", "nav.extract": "এআই এক্সট্রাকশন",
      "nav.review": "মানব পর্যালোচনা", "nav.portal": "সরকারি পোর্টাল", "nav.status": "আবেদনের অবস্থা",
      "nav.settings": "সেটিংস",
      "dashboard.greeting": "নমস্কার! আজ আপনি কী করতে চান?",
      "dashboard.chatSend": "সহায়.AI-কে জিজ্ঞাসা করুন",
      "dashboard.continue": "আবেদন চালিয়ে যান", "dashboard.track": "আবেদন ট্র্যাক করুন", "dashboard.newApp": "নতুন অনুরোধ শুরু করুন",
      "dashboard.recent": "সাম্প্রতিক আবেদন",
      "chat.inputPlaceholder": "আপনার বার্তা টাইপ করুন...", "chat.send": "পাঠান", "chat.startOver": "আবার শুরু করুন",
      "step.upload": "আপলোড", "step.validate": "যাচাইকরণ", "step.extract": "এক্সট্রাকশন",
      "step.review": "মানব পর্যালোচনা", "step.portal": "সরকারি পোর্টাল", "step.completed": "সম্পন্ন",
    },
  };

  const SUGGESTED_PROMPTS = [
    "I want to apply for an old age pension",
    "I need to update my KYC details",
    "Track my existing application",
    "What documents do I need?",
  ];

  let currentLanguage = localStorage.getItem("sahaay_ui_language") || "en";

  function t(key) {
    return (I18N[currentLanguage] && I18N[currentLanguage][key]) || I18N.en[key] || key;
  }

  function applyTranslations() {
    document.documentElement.lang = currentLanguage;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const translated = t(key);
      const firstChild = el.childNodes[0];
      if (firstChild && firstChild.nodeType === Node.TEXT_NODE && el.children.length > 0) {
        firstChild.textContent = translated + " ";
      } else if (el.children.length === 0) {
        el.textContent = translated;
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    document.getElementById("language-select").value = currentLanguage;
    const settingsSelect = document.getElementById("language-select-settings");
    if (settingsSelect) settingsSelect.value = currentLanguage;
    renderStepperLabels();
    renderSuggestedPrompts();
    updatePageHeader(getCurrentPage());
  }

  function setLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem("sahaay_ui_language", lang);
    applyTranslations();
  }

  function populateSettingsLanguageSelect() {
    const select = document.getElementById("language-select-settings");
    const headerSelect = document.getElementById("language-select");
    select.innerHTML = headerSelect.innerHTML;
    select.addEventListener("change", () => setLanguage(select.value));
  }

  document.getElementById("language-select").addEventListener("change", (event) => {
    setLanguage(event.target.value);
  });

  /* ------------------------------------------------------------------ */
  /* Router — hash-based, page = <section class="page" data-page="...">  */
  /* ------------------------------------------------------------------ */

  const PAGES = ["dashboard", "chat", "upload", "validate", "extract", "review", "portal", "status", "support", "settings"];

  function getCurrentPage() {
    const hash = (window.location.hash || "#dashboard").replace("#", "");
    return PAGES.includes(hash) ? hash : "dashboard";
  }

  function updatePageHeader(page) {
    const titleKey = `pageTitle.${page}`;
    const subtitleKey = `pageSubtitle.${page}`;
    document.getElementById("page-title").textContent = t(titleKey) !== titleKey ? t(titleKey) : capitalize(page);
    document.getElementById("page-subtitle").textContent = t(subtitleKey) !== subtitleKey ? t(subtitleKey) : "";
  }

  function capitalize(value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function navigateTo(page) {
    if (!PAGES.includes(page)) page = "dashboard";
    document.querySelectorAll(".page").forEach((section) => {
      section.classList.toggle("is-active", section.dataset.page === page);
    });
    document.querySelectorAll(".nav-item, .nav-subitem").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.page === page);
    });
    document.getElementById("workflow-stepper").hidden = !["upload", "validate", "extract", "review", "portal", "status"].includes(page);
    document.querySelectorAll(".step").forEach((step) => {
      step.classList.toggle("is-current", step.dataset.step === page);
    });
    updatePageHeader(page);
    closeSidebarOnMobile();
    if (page === "dashboard") renderDashboard();
    if (typeof updateTakeControlPanel === "function") updateTakeControlPanel(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  window.addEventListener("hashchange", () => navigateTo(getCurrentPage()));

  document.querySelectorAll(".nav-item, .nav-subitem, [data-page]").forEach((el) => {
    el.addEventListener("click", (event) => {
      const page = el.dataset.page;
      if (!page) return;
      window.location.hash = `#${page}`;
    });
  });

  /* ------------------------------------------------------------------ */
  /* Sidebar (mobile toggle)                                             */
  /* ------------------------------------------------------------------ */

  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("sidebar-scrim");

  document.getElementById("sidebar-toggle").addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("is-open");
    scrim.hidden = !isOpen;
  });
  scrim.addEventListener("click", closeSidebarOnMobile);

  function closeSidebarOnMobile() {
    sidebar.classList.remove("is-open");
    scrim.hidden = true;
  }

  document.querySelector(".nav-group-toggle").addEventListener("click", (event) => {
    event.currentTarget.closest(".nav-group").classList.toggle("is-expanded");
  });

  /* ------------------------------------------------------------------ */
  /* Workflow stepper — navigational always; "completed" markers use     */
  /* lightweight, non-invasive observers on app.js's own result panels   */
  /* rather than re-implementing any business logic here.                */
  /* ------------------------------------------------------------------ */

  function renderStepperLabels() {
    document.querySelectorAll(".step .step-label").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
  }

  function markStepDone(stepName) {
    const step = document.querySelector(`.step[data-step="${stepName}"]`);
    if (step) step.classList.add("is-done");
  }

  function observeText(elementId, callback) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const observer = new MutationObserver(() => callback(el.textContent.trim()));
    observer.observe(el, { childList: true, characterData: true, subtree: true });
  }

  observeText("upload-result", (text) => { if (text && !/fail|error/i.test(text)) markStepDone("upload"); });
  observeText("validation-result", (text) => { if (text) markStepDone("validate"); });
  observeText("extract-result", (text) => { if (text) markStepDone("extract"); });
  observeText("gov-app-status", (text) => {
    if (text) markStepDone("review");
    if (/submitted/i.test(text)) markStepDone("completed");
  });
  observeText("portal-feedback", (text) => { if (text && !/cancel|error|pause/i.test(text)) markStepDone("portal"); });

  /* ------------------------------------------------------------------ */
  /* Recent applications (Dashboard) — tracked client-side only, from    */
  /* the same #gov-app-id element app.js already fills in on intake/load.*/
  /* No new backend calls; there is no "list applications" endpoint.     */
  /* ------------------------------------------------------------------ */

  const RECENTS_KEY = "sahaay_recent_applications";

  function getRecents() {
    try {
      return JSON.parse(localStorage.getItem(RECENTS_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function rememberApplication(applicationId, status) {
    if (!applicationId) return;
    let recents = getRecents().filter((entry) => entry.id !== applicationId);
    recents.unshift({ id: applicationId, status: status || "", ts: Date.now() });
    recents = recents.slice(0, 5);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(recents));
    renderDashboard();
  }

  observeText("gov-app-id", (text) => {
    if (text) rememberApplication(text, document.getElementById("gov-app-status").textContent.trim());
  });
  observeText("gov-app-status", (text) => {
    const appId = document.getElementById("gov-app-id").textContent.trim();
    if (appId) rememberApplication(appId, text);
  });

  function timeAgo(ts) {
    const seconds = Math.floor((Date.now() - ts) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function renderDashboard() {
    const recents = getRecents();
    const listEl = document.getElementById("dashboard-recent-list");
    const continueDesc = document.getElementById("card-continue-desc");

    if (recents.length === 0) {
      listEl.innerHTML = `<p class="dashboard-recent-empty">${t("dashboard.recentEmpty")}</p>`;
      continueDesc.textContent = t("dashboard.continueDesc");
      return;
    }

    continueDesc.textContent = `${recents[0].id} — ${recents[0].status || "in progress"}`;
    listEl.innerHTML = recents
      .map(
        (entry) => `
        <button type="button" class="recent-app-row" data-app-id="${escapeAttr(entry.id)}">
          <span class="recent-app-id">${escapeText(entry.id)}</span>
          <span class="recent-app-status">${escapeText(entry.status || "—")}</span>
          <span class="recent-app-time">${timeAgo(entry.ts)}</span>
        </button>`
      )
      .join("");
    listEl.querySelectorAll(".recent-app-row").forEach((row) => {
      row.addEventListener("click", () => openApplicationInReview(row.dataset.appId));
    });
  }

  function escapeText(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }
  function escapeAttr(value) {
    return escapeText(value).replace(/"/g, "&quot;");
  }

  function openApplicationInReview(applicationId) {
    window.location.hash = "#review";
    const loadInput = document.getElementById("gov-load-application-id");
    const loadBtn = document.getElementById("gov-load-application-btn");
    loadInput.value = applicationId;
    loadBtn.click();
  }

  document.getElementById("card-continue").addEventListener("click", () => {
    const recents = getRecents();
    if (recents.length > 0) {
      openApplicationInReview(recents[0].id);
    } else {
      window.location.hash = "#chat";
    }
  });
  document.getElementById("card-track").addEventListener("click", () => {
    window.location.hash = "#status";
  });
  document.getElementById("card-new").addEventListener("click", () => {
    window.location.hash = "#chat";
  });

  document.getElementById("dashboard-chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("dashboard-chat-input");
    const text = input.value.trim();
    if (!text) {
      window.location.hash = "#chat";
      return;
    }
    window.location.hash = "#chat";
    const chatInput = document.getElementById("conversation-input");
    chatInput.value = text;
    input.value = "";
    setTimeout(() => document.getElementById("conversation-form").requestSubmit(), 50);
  });

  /* ------------------------------------------------------------------ */
  /* Application Status page — hands off to Human Review for full detail */
  /* ------------------------------------------------------------------ */

  document.getElementById("status-lookup-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const id = document.getElementById("status-lookup-id").value.trim();
    if (!id) return;
    document.getElementById("status-lookup-result").innerHTML =
      `<p>Opening application <strong>${escapeText(id)}</strong> in Human Review…</p>`;
    openApplicationInReview(id);
  });

  /* ------------------------------------------------------------------ */
  /* Suggested prompts (Dashboard + Chat)                                 */
  /* ------------------------------------------------------------------ */

  function renderSuggestedPrompts() {
    [document.getElementById("dashboard-suggested-prompts"), document.getElementById("chat-suggested-prompts")].forEach(
      (container) => {
        if (!container) return;
        container.innerHTML = SUGGESTED_PROMPTS.map(
          (prompt) => `<button type="button" class="prompt-chip">${escapeText(prompt)}</button>`
        ).join("");
        container.querySelectorAll(".prompt-chip").forEach((chip, index) => {
          chip.addEventListener("click", () => {
            const text = SUGGESTED_PROMPTS[index];
            if (container.id === "dashboard-suggested-prompts") {
              document.getElementById("dashboard-chat-input").value = text;
              document.getElementById("dashboard-chat-form").requestSubmit();
            } else {
              document.getElementById("conversation-input").value = text;
              document.getElementById("conversation-form").requestSubmit();
            }
          });
        });
      }
    );
  }

  /* ------------------------------------------------------------------ */
  /* Chat UI extras: typing indicator, voice input, file-upload shortcut  */
  /* ------------------------------------------------------------------ */

  const typingIndicator = document.getElementById("conversation-typing");
  const conversationForm = document.getElementById("conversation-form");
  const conversationSendBtn = document.getElementById("conversation-send-btn");

  const sendBtnObserver = new MutationObserver(() => {
    const isBusy = conversationSendBtn.disabled;
    typingIndicator.hidden = !isBusy;
  });
  sendBtnObserver.observe(conversationSendBtn, { attributes: true, attributeFilter: ["disabled"] });

  document.getElementById("chat-file-btn").addEventListener("click", () => {
    window.location.hash = "#upload";
  });

  const voiceBtn = document.getElementById("voice-input-btn");
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognitionImpl) {
    voiceBtn.disabled = true;
    voiceBtn.title = "Voice input is not supported in this browser";
  } else {
    let recognition = null;
    let listening = false;
    voiceBtn.addEventListener("click", () => {
      if (listening) {
        recognition && recognition.stop();
        return;
      }
      recognition = new SpeechRecognitionImpl();
      recognition.lang = { en: "en-IN", hi: "hi-IN", mr: "mr-IN", ta: "ta-IN", te: "te-IN", bn: "bn-IN", kn: "kn-IN" }[currentLanguage] || "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        listening = true;
        voiceBtn.classList.add("is-listening");
      };
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById("conversation-input").value = transcript;
      };
      recognition.onerror = () => {
        listening = false;
        voiceBtn.classList.remove("is-listening");
      };
      recognition.onend = () => {
        listening = false;
        voiceBtn.classList.remove("is-listening");
      };
      recognition.start();
    });
  }

  let kannadaNoticeShown = false;
  conversationForm.addEventListener(
    "submit",
    () => {
      if (!SUPPORTED_CHAT_LANGUAGES.has(currentLanguage) && !kannadaNoticeShown) {
        kannadaNoticeShown = true;
        const note = document.createElement("div");
        note.className = "conversation-bubble conversation-bubble-sahaay conversation-bubble-notice";
        note.textContent = t("chat.kannadaNotice");
        document.getElementById("conversation-window").appendChild(note);
      }
    },
    true
  );

  /* ------------------------------------------------------------------ */
  

  /* ------------------------------------------------------------------ */
  /* Take Control mode — a persistent assistant panel that stays visible  */
  /* across every page once enabled, explaining the current step and     */
  /* offering an always-available exit. Purely presentational: it reads  */
  /* the current page/stepper state and never touches any backend call.  */
  /* ------------------------------------------------------------------ */

  let takeControlActive = false;
  const takeControlToggleBtn = document.getElementById("take-control-toggle");
  const takeControlPanel = document.getElementById("take-control-panel");
  const takeControlStepText = document.getElementById("take-control-step-text");
  const takeControlExitBtn = document.getElementById("take-control-exit");

  function updateTakeControlPanel(page) {
    if (!takeControlActive) return;
    const key = `takeControl.${page}`;
    const translated = t(key);
    takeControlStepText.textContent = translated !== key ? translated : t("takeControl.on");
  }

  function setTakeControl(active) {
    takeControlActive = active;
    takeControlToggleBtn.classList.toggle("is-active", active);
    takeControlToggleBtn.setAttribute("aria-pressed", String(active));
    takeControlPanel.hidden = !active;
    if (active) updateTakeControlPanel(getCurrentPage());
  }

  takeControlToggleBtn.addEventListener("click", () => setTakeControl(!takeControlActive));
  takeControlExitBtn.addEventListener("click", () => setTakeControl(false));

  /* ------------------------------------------------------------------ */
  /* Human Governance consent gate — when the loaded application         */
  /* touches sensitive data (Aadhaar, PAN, bank details, etc.), the       */
  /* normal review form stays hidden behind a plain-language consent      */
  /* prompt until the citizen agrees. This wraps app.js's own             */
  /* renderGovApplication (a global function, since app.js is a classic   */
  /* script) rather than duplicating its rendering logic — every field,   */
  /* button, and API call it wires up still happens exactly as before,    */
  /* this only decides whether that markup is shown immediately or after  */
  /* consent.                                                             */
  /* ------------------------------------------------------------------ */

  const SENSITIVE_FIELD_PATTERN = /aadhaar|pan\b|pan_number|account|ifsc|bank|card.?number|passport/i;
  const consentedApplications = new Set();

  const consentGate = document.getElementById("governance-consent-gate");
  const consentFieldsEl = document.getElementById("governance-consent-fields");
  const govReviewBody = document.getElementById("gov-review-body");
  const consentAcceptBtn = document.getElementById("governance-consent-accept");
  const consentDeclineBtn = document.getElementById("governance-consent-decline");

  function revealGovReviewBody() {
    consentGate.hidden = true;
    govReviewBody.classList.remove("is-gated");
  }

  if (typeof window.renderGovApplication === "function") {
    const originalRenderGovApplication = window.renderGovApplication;
    window.renderGovApplication = function (data) {
      originalRenderGovApplication(data);

      const sensitiveFields = (data.fields || []).filter(
        (field) => SENSITIVE_FIELD_PATTERN.test(field.field || "") || SENSITIVE_FIELD_PATTERN.test(field.source_document || "")
      );

      if (sensitiveFields.length === 0 || consentedApplications.has(data.application_id)) {
        revealGovReviewBody();
        return;
      }

      consentFieldsEl.textContent = sensitiveFields.map((field) => field.field).join(", ");
      consentGate.hidden = false;
      govReviewBody.classList.add("is-gated");
    };
  }

  consentAcceptBtn.addEventListener("click", () => {
    if (currentGovApplicationId()) consentedApplications.add(currentGovApplicationId());
    revealGovReviewBody();
  });

  consentDeclineBtn.addEventListener("click", () => {
    // Stay gated — the review form underneath is left untouched (never
    // emptied or removed) so accepting later still works normally.
    govReviewBody.classList.add("is-gated");
    consentFieldsEl.textContent = t("govGate.declinedNotice");
  });

  function currentGovApplicationId() {
    const idEl = document.getElementById("gov-app-id");
    return idEl ? idEl.textContent.trim() : null;
  }

  /* ------------------------------------------------------------------ */
  /* Init                                                                 */
  /* ------------------------------------------------------------------ */

  populateSettingsLanguageSelect();
  applyTranslations();
  navigateTo(getCurrentPage());
  renderDashboard();
})();
