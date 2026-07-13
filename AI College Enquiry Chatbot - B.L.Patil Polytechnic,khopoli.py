import re
import threading
from datetime import datetime
from tkinter import *
from tkinter import filedialog, messagebox
from tkinter import ttk

import nltk
import pyttsx3
import speech_recognition as sr
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Ensure necessary NLTK components are safely downloaded
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)

stemmer = PorterStemmer()


# --- UPDATED SMOOTH FEMALE AUDIO PIPELINE ---
def speak_text(text):
    """Speak text cleanly using an explicit female system voice inside a dedicated lifecycle thread."""
    # Strip markdown headers, bold symbols, bullet points, and emojis
    clean_text = re.sub(
        r"[\*_🤖💻⚙️⚡🏗️📡📖💼🎓🎯💰🍔🏆📞👋🏢•]", "", text
    ).strip()

    if not clean_text:
        return

    def run_speech():
        try:
            # Initializing locally inside the worker thread avoids cross-thread audio channel freezes
            local_engine = pyttsx3.init()
            local_engine.setProperty("rate", 165)

            # --- SEARCH AND ASSIGN FEMALE VOICE ---
            voices = local_engine.getProperty("voices")
            for voice in voices:
                # Check if 'female' or 'woman' is listed inside the voice description ID tags
                if "female" in voice.name.lower() or "Zira" in voice.name:
                    local_engine.setProperty("voice", voice.id)
                    break
            else:
                # Fallback: If no explicit string match, try selecting index 1 (traditionally female on Windows)
                if len(voices) > 1:
                    local_engine.setProperty("voice", voices[1].id)

            local_engine.say(clean_text)
            local_engine.runAndWait()

            # Cleanly close and drop local reference to open the driver back up immediately
            local_engine.stop()
            del local_engine
        except Exception as e:
            print(f"TTS Thread Exception: {e}")

    threading.Thread(target=run_speech, daemon=True).start()


def listen_mic():
    """Capture audio input using a separate background thread and feed it into the chatbot entry."""
    recognizer = sr.Recognizer()

    def run_listening():
        root.after(0, lambda: btn_mic.config(text="🎤 Listening...", bg="#EF4444"))
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            try:
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=5)
                query = recognizer.recognize_google(audio)

                # Send text directly to user interfaces safely
                root.after(0, lambda: entry.delete(0, END))
                root.after(0, lambda: entry.insert(0, query))
                root.after(0, lambda: send())
            except sr.UnknownValueError:
                root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Audio Input", "Could not interpret your speech. Try again!"
                    ),
                )
            except sr.RequestError:
                root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Audio Input", "Speech recognition service is offline."
                    ),
                )
            except Exception:
                pass
            finally:
                root.after(
                    0, lambda: btn_mic.config(text="🎤 Mic", bg="#0284C7")
                )

    threading.Thread(target=run_listening, daemon=True).start()


def preprocess_text(text):
    """Clean, tokenize, and stem text for robust matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    tokens = nltk.word_tokenize(text)
    stemmed_tokens = [stemmer.stem(token) for token in tokens]
    return " ".join(stemmed_tokens)


# ==========================================
# GRANULAR KNOWLEDGE BASE CONFIGURATION
# ==========================================
KNOWLEDGE_BASE = {
    "hello hi hey greetings welcome good morning afternoon": "Hello! 👋 Welcome to B.L.Patil Polytechnic, Khopoli. How can I help you today?",
    "about us college history vision institute trust info overview": "🏢 **About B.L.Patil Polytechnic:**\nEstablished to provide quality technical education, our institute is approved by AICTE New Delhi, recognized by the Government of Maharashtra, and affiliated with MSBTE. We strive to nurture skilled, industry-ready engineering professionals.",
    "courses programs degree departments branches engineering": "📚 **Courses Offered (3-Year Diploma):**\nChoose a quick department filter below or type a branch name to see specific seat allocations and details!",
    "computer engineering comp co cse software hardware coding computer": "💻 **Computer Engineering**\n• Duration: 3 Years\n• Intake Capacity: 60 Seats\n• Focus: Software development, databases, operating systems, and computer networking.",
    "artificial intelligence machine learning ai ml data science programming python": "🤖 **Artificial Intelligence & Machine Learning**\n• Duration: 3 Years\n• Intake Capacity: 60 Seats\n• Focus: Data analytics, neural networks, predictive modeling, and Python automation.",
    "mechanical engineering mech me design car manufacturing cad cam workshop": "⚙️ **Mechanical Engineering**\n• Duration: 3 Years\n• Intake Capacity: 60 Seats\n• Focus: Thermal design, manufacturing systems, CAD/CAM, and industrial automation.",
    "electrical engineering ee elect power wire solar current voltage grid": "⚡ **Electrical Engineering**\n• Duration: 3 Years\n• Intake Capacity: 60 Seats\n• Focus: Power systems, electrical machines, transmission grids, and green energy models.",
    "civil engineering ce civil structural building construction map blueprint surveying": "🏗️ **Civil Engineering**\n• Duration: 3 Years\n• Intake Capacity: 60 Seats\n• Focus: Structural blueprinting, environmental infrastructure, surveying, and construction management.",
    "electronics telecommunication extc ej iot signal chip network hardware": "📡 **Electronics & Telecommunication**\n• Duration: 3 Years\n• Intake Capacity: 30 Seats\n• Focus: Embedded microcontrollers, signal processing, IoT routing, and wireless infrastructure.",
    "syllabus curriculum subjects subjects studied exam test semester msbte": "📖 **Curriculum Overview:**\nThe academic path aligns with the MSBTE 'K/I' schemes, pairing core foundational mathematics and sciences with targeted lab assignments and field electives starting in your second year.",
    "placements jobs salary careers recruiting companies recruitment packag hire": "💼 **Placement & Training Cell:**\nOur cell links engineering candidates with leading industrial estates across the Khopoli-Rasayani-Patalganga manufacturing belts and regional IT hubs.",
    "eligibility criteria tenth ssc qualifications marks required requirement admission eligibility pass": "🎓 **Eligibility Requirements:**\nApplicants must have passed the 10th Standard (SSC) examination with a minimum total score of 35% as dictated by the DTE Maharashtra selection standards.",
    "admission apply admission process documents registration cap round online dte merit": "🎯 **Admission Process:**\nAdmissions are strictly merit-based following 10th standard (SSC) results via DTE Maharashtra CAP rounds. Required documents include your 10th Marksheet, LC/TC, and valid identity verification cards.",
    "fees fee cost tuition payments concessions scholarships fra money pay cost": "💰 **Fee Structure:**\nFees are regulated annually by the Shikshan Shulka Samiti (FRA) Maharashtra. Please visit the admission office block or the official DTE portal for exact category concessions.",
    "scholarships financial aid mahadbt tfws ebc concession freeship grant": "🎓 **Scholarships & Concessions:**\nEligible candidates can apply for various government financial aid options including MahaDBT schemes, EBC concessions, TFWS allocations, and category-based freeships (SC/ST/OBC/VJNT). Make sure to submit income and caste documents during registration.",
    "hostel accommodation stay rooms flat paying guest pg room live rent": "🏢 **Hostel Facility:**\nThere are no official institutional hostels inside the campus. Outstation students generally opt for private hostels or rental rooms nearby in Khopoli.",
    "library books study materials digital journals reading room borrow novel": "📖 Our library has over 21,000 reference books and multiple digital engineering journals for academic research.",
    "canteen food cafeteria lunch snacks mess eat plate meal dish": "🍔 The campus has a clean canteen serving hygienic, pocket-friendly meals and snacks.",
    "sports events cultural festival activities gathering tournament gathering": "🏆 **Campus Life, Sports & Events:**\nWe organize annual state-level technical events, Inter-Engineering sports tournaments, cultural gatherings, and regular industrial exposure visits to promote all-round development.",
    "contact us phone number address location map email office timing telephone query": "📞 **Contact & Location Info:**\n• **Address:** Khopoli, Dist. Raigad, Maharashtra\n• **Office Hours:** 10:00 AM to 5:00 PM (Monday to Saturday)\n• **Telephone Number:** +91 2192 263744\n• **Email:** contact@blpatilpolytechnic.edu.in\n• **Enquiry Desk:** Please visit the main administrative building for personalized validation.",
    "bye exit close leave quit thank you thanks": "Thank you for visiting our portal. Have a wonderful day ahead! 😊",
}

CONTEXTUAL_DEEP_DIVES = {
    "computer": {
        "syllabus": "📖 **Computer Eng. Syllabus:**\nFocuses on C/C++, Java, Advanced Database Management Systems, Data Structures, Linux Administration, and Software Engineering methodologies across 6 semesters.",
        "placements": "💼 **Computer Eng. Placements:**\nExcellent track record with placements in regional software setups, tech consultancies, and IT maintenance sectors around Navi Mumbai and Pune belts.",
        "eligibility": "🎓 **Computer Eng. Eligibility:**\nPassed 10th Std. (SSC) with min. 35% aggregate marks. Strong affinity for logical math and basic computer operations recommended.",
    },
    "ai & ml": {
        "syllabus": "🤖 **AI & ML Syllabus:**\nIncludes Python programming, foundational Data Science, Introduction to Machine Learning models, Neural Networks, and cloud computing deployment schemes.",
        "placements": "💼 **AI & ML Placements:**\nHigh demand in modern analytics firms, automation cells within major industries, and technology startups seeking data engineering specialists.",
        "eligibility": "🎓 **AI & ML Eligibility:**\nStandard DTE requirement (10th pass with 35%). Recommended clear fundamentals in statistics and computing basics.",
    },
    "mechanical": {
        "syllabus": "⚙️ **Mechanical Eng. Syllabus:**\nCovers Engineering Mechanics, Strength of Materials, CAD/CAM design tools, Thermal Engineering, Metrology, and Fluid Power systems.",
        "placements": "💼 **Mechanical Eng. Placements:**\nDirect access to Khopoli manufacturing zones, steel complexes, automotive parts suppliers, and fabrication plants.",
        "eligibility": "🎓 **Mechanical Eng. Eligibility:**\n10th Pass with 35% aggregate. General medical fitness required for industrial workshop programs.",
    },
    "electrical": {
        "syllabus": "⚡ **Electrical Eng. Syllabus:**\nCovers Fundamentals of Electrical Engineering, AC/DC Machines, Power Systems Generation, Switchgear & Protection, and Electrical Estimation.",
        "placements": "💼 **Electrical Eng. Placements:**\nRecruiters include state electricity bodies, heavy electrical machinery plants, solar grid installation contracts, and processing units.",
        "eligibility": "🎓 **Electrical Eng. Eligibility:**\n10th Pass with 35% aggregate marks under standard DTE regulations.",
    },
    "civil": {
        "syllabus": "🏗️ **Civil Eng. Syllabus:**\nTopics feature Surveying, Building Construction materials, Concrete Technology, Geotechnical Engineering, Estimating & Costing, and Highway Infrastructure.",
        "placements": "💼 **Civil Eng. Placements:**\nPlacements with infrastructural developers, structural design firms, local civil construction agencies, and real estate groups.",
        "eligibility": "🎓 **Civil Eng. Eligibility:**\n10th Pass with 35% aggregate marks. Requires basic technical drawing skills.",
    },
    "extc": {
        "syllabus": "📡 **EXTC Eng. Syllabus:**\nEmphasizes Electronic Devices, Digital Techniques, Microcontrollers, Principles of Communication Systems, Embedded Systems, and IoT sensor loops.",
        "placements": "💼 **EXTC Eng. Placements:**\nOpportunities span telecom service providers, embedded hardware production teams, automation suppliers, and industrial network companies.",
        "eligibility": "🎓 **EXTC Eng. Eligibility:**\n10th Pass with 35% aggregate score following standard CAP assignment regulations.",
    },
}

PREDICTIVE_SUGGESTIONS = {
    "About College Profile": "about us",
    "Admission Process & Eligibility": "admission",
    "Computer Engineering Details": "computer",
    "AI & Machine Learning Details": "ai",
    "Mechanical Engineering Details": "mechanical",
    "Electrical Engineering Details": "electrical",
    "Civil Engineering Details": "civil",
    "Electronics & Telecommunication": "extc",
    "Fee Structures & Concessions": "fees",
    "Scholarships & Financial Aid": "scholarships",
    "Syllabus & MSBTE Schemes": "syllabus",
    "Placements & Recruitment Hubs": "placements",
    "Hostel Accommodations": "hostel",
    "Library Reference Material": "library",
    "Campus Canteen Services": "canteen",
    "Sports & Campus Events": "sports",
    "Contact Office & Location": "contact us",
}

processed_questions = [preprocess_text(q) for q in KNOWLEDGE_BASE.keys()]
answers = list(KNOWLEDGE_BASE.values())
vectorizer = TfidfVectorizer()
X_matrix = vectorizer.fit_transform(processed_questions)

current_topic_context = "main"
selected_branch_context = ""

chat_history_log = []
is_dark_mode = False

THEMES = {
    "light": {
        "bg": "#F1F5F9",
        "bubble_user": "#E2F1E7",
        "bubble_bot": "#FFFFFF",
        "text": "#1E293B",
        "subtext": "#64748B",
        "border_user": "#A7F3D0",
        "border_bot": "#CBD5E1",
    },
    "dark": {
        "bg": "#0F172A",
        "bubble_user": "#1E293B",
        "bubble_bot": "#334155",
        "text": "#F8FAFC",
        "subtext": "#94A3B8",
        "border_user": "#0F766E",
        "border_bot": "#475569",
    },
}


def toggle_theme():
    """Toggles the theme layout seamlessly across active user interface scopes."""
    global is_dark_mode
    is_dark_mode = not is_dark_mode
    current_theme = "dark" if is_dark_mode else "light"
    colors = THEMES[current_theme]

    root.configure(bg=colors["bg"])
    canvas_frame.configure(bg=colors["bg"])
    canvas.configure(bg=colors["bg"])
    scrollable_frame.configure(bg=colors["bg"])
    opt_label.configure(bg=colors["bg"], fg=colors["subtext"])
    opt_frame.configure(bg=colors["bg"])
    bottom.configure(bg=colors["bg"])

    for row_frame in scrollable_frame.winfo_children():
        row_frame.configure(bg=colors["bg"])
        for border_frame in row_frame.winfo_children():
            for inner_bubble in border_frame.winfo_children():
                is_user_bubble = (
                    inner_bubble.cget("bg") == THEMES["light"]["bubble_user"]
                    or inner_bubble.cget("bg") == THEMES["dark"]["bubble_user"]
                )
                if is_user_bubble:
                    border_frame.configure(bg=colors["border_user"])
                    inner_bubble.configure(bg=colors["bubble_user"])
                else:
                    border_frame.configure(bg=colors["border_bot"])
                    inner_bubble.configure(bg=colors["bubble_bot"])

                for widget in inner_bubble.winfo_children():
                    if isinstance(widget, Label):
                        if "italic" in str(widget.cget("font")):
                            widget.configure(
                                bg=colors["bubble_user"]
                                if is_user_bubble
                                else colors["bubble_bot"],
                                fg=colors["subtext"],
                            )
                        else:
                            widget.configure(
                                bg=colors["bubble_user"]
                                if is_user_bubble
                                else colors["bubble_bot"],
                                fg=colors["text"],
                            )

    btn_theme.configure(text="☀️ Light Mode" if is_dark_mode else "🌙 Dark Mode")


def export_chat():
    """Saves conversation strings log out safely into a chosen text directory."""
    if not chat_history_log:
        messagebox.showinfo("Export Panel", "No conversation history to export yet!")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Documents", "*.txt"), ("All Files", "*.*")],
        title="Export Chat Log",
        initialfile=f"BL_Patil_Chat_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    )

    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(
                    f"=========================================\n"
                    f" B.L.PATIL POLYTECHNIC HELPDESK CHAT LOG\n"
                    f" Exported on: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                    f"=========================================\n\n"
                )
                for entry in chat_history_log:
                    file.write(f"{entry}\n")
            messagebox.showinfo("Export Panel", "Chat log exported successfully!")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save file:\n{e}")


def chatbot_response(user_text):
    global current_topic_context, selected_branch_context
    lowered = user_text.lower().strip()

    if (
        current_topic_context == "course_deep_dive"
        and selected_branch_context in CONTEXTUAL_DEEP_DIVES
    ):
        if lowered in CONTEXTUAL_DEEP_DIVES[selected_branch_context]:
            return CONTEXTUAL_DEEP_DIVES[selected_branch_context][lowered]

    processed_user = preprocess_text(user_text)
    if not processed_user.strip():
        return "I didn't quite catch that. Could you please rephrase your query?"

    try:
        user_vector = vectorizer.transform([processed_user])
        similarity = cosine_similarity(user_vector, X_matrix)
        index = similarity.argmax()
        score = similarity[0][index]
    except Exception:
        score = 0.0

    if score > 0.35:
        return answers[index]
    elif score > 0.12:
        return f"✨ **Suggested Match:**\n\n{answers[index]}"

    if any(q_word in lowered for q_word in ["how", "where", "what", "why"]):
        return "🔍 I couldn't locate precise data matching your entry. Try tapping one of our quick resource buttons below or head over to the main administrative panel."
    return "Sorry, I couldn't find an exact match for your inquiry. 💡 Try selecting an explicit category filter below."


def check_key_release(event):
    value = event.widget.get().strip().lower()

    if not value:
        prediction_box.place_forget()
        return

    matches = [
        title
        for title in PREDICTIVE_SUGGESTIONS.keys()
        if value in title.lower() or value in PREDICTIVE_SUGGESTIONS[title]
    ]

    if matches:
        prediction_box.delete(0, END)
        for selection in matches[:4]:
            prediction_box.insert(END, selection)

        prediction_box.place(
            x=entry_container.winfo_x(),
            y=bottom.winfo_y() - prediction_box.winfo_reqheight() - 10,
            width=entry_container.winfo_width(),
        )
    else:
        prediction_box.place_forget()


def on_prediction_select(event):
    if not prediction_box.curselection():
        return
    chosen_index = prediction_box.curselection()[0]
    display_text = prediction_box.get(chosen_index)

    actual_query = PREDICTIVE_SUGGESTIONS[display_text]
    prediction_box.place_forget()
    entry.delete(0, END)
    send(actual_query)


def add_bubble(text, is_user=True):
    current_time = datetime.now().strftime("%I:%M %p")
    current_theme = "dark" if is_dark_mode else "light"
    colors = THEMES[current_theme]

    sender_tag = "USER" if is_user else "BOT"
    chat_history_log.append(f"[{current_time}] {sender_tag}: {text}")

    bubble_bg = colors["bubble_user"] if is_user else colors["bubble_bot"]
    border_bg = colors["border_user"] if is_user else colors["border_bot"]
    frame_anchor = "e" if is_user else "w"

    row_frame = Frame(scrollable_frame, bg=colors["bg"])
    row_frame.pack(fill="x", pady=8, anchor=frame_anchor)

    bubble_border = Frame(row_frame, bg=border_bg, bd=1)
    bubble_border.pack(anchor=frame_anchor, padx=18)

    bubble = Frame(bubble_border, bg=bubble_bg, bd=0, padx=16, pady=12)
    bubble.pack()

    lbl_msg = Label(
        bubble,
        text=text,
        font=("Segoe UI/Arial", 11),
        bg=bubble_bg,
        fg=colors["text"],
        justify=LEFT,
        wraplength=460,
    )
    lbl_msg.pack(anchor="w")

    lbl_time = Label(
        bubble,
        text=current_time,
        font=("Segoe UI", 8, "italic"),
        bg=bubble_bg,
        fg=colors["subtext"],
    )
    lbl_time.pack(anchor="e", pady=(6, 0))

    scrollable_frame.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.yview_moveto(1.0)

    # Trigger audio cleanly on bot replies without blocking UI
    if not is_user:
        speak_text(text)


def send(custom_msg=None):
    global current_topic_context, selected_branch_context
    prediction_box.place_forget()

    msg = custom_msg if custom_msg else entry.get().strip()
    if not msg:
        return

    add_bubble(msg, is_user=True)
    if not custom_msg:
        entry.delete(0, END)

    if msg.lower() in ["exit", "bye", "quit"]:
        root.after(1200, root.destroy)
        return

    reply = chatbot_response(msg)
    root.after(200, lambda: add_bubble(reply, is_user=False))

    lowered_msg = msg.lower()

    if any(
        k in lowered_msg
        for k in ["course", "program", "branch", "dept", "department"]
    ):
        current_topic_context = "courses"
        root.after(250, show_courses_submenu)
    elif "computer" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "computer"
        root.after(250, show_deep_dive_context)
    elif "ai" in lowered_msg or "ml" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "ai & ml"
        root.after(250, show_deep_dive_context)
    elif "mechanical" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "mechanical"
        root.after(250, show_deep_dive_context)
    elif "electrical" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "electrical"
        root.after(250, show_deep_dive_context)
    elif "civil" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "civil"
        root.after(250, show_deep_dive_context)
    elif "extc" in lowered_msg or "telecommunication" in lowered_msg:
        current_topic_context = "course_deep_dive"
        selected_branch_context = "extc"
        root.after(250, show_deep_dive_context)


def clear_chat():
    global current_topic_context, selected_branch_context, chat_history_log
    prediction_box.place_forget()
    chat_history_log.clear()
    for widget in scrollable_frame.winfo_children():
        widget.destroy()
    add_bubble(
        "🤖 Welcome to B.L.Patil Polytechnic Helpdesk! How can I assist you today?",
        is_user=False,
    )
    current_topic_context = "main"
    selected_branch_context = ""
    show_main_menu()


def clear_options_frame():
    for widget in opt_frame.winfo_children():
        widget.destroy()


def create_styled_button(parent, text, command, type_flag="primary"):
    if type_flag == "primary":
        bg_col, hvr_col = "#0F766E", "#115E59"
    elif type_flag == "accent":
        bg_col, hvr_col = "#0284C7", "#0369A1"
    else:
        bg_col, hvr_col = "#64748B", "#475569"

    btn = Button(
        parent,
        text=text,
        font=("Segoe UI", 9, "bold"),
        bg=bg_col,
        fg="white",
        activebackground=hvr_col,
        activeforeground="white",
        relief="flat",
        cursor="hand2",
        command=command,
        bd=0,
        pady=6,
    )

    btn.bind("<Enter>", lambda e: btn.config(bg=hvr_col))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg_col))
    return btn


def show_main_menu():
    global current_topic_context, selected_branch_context
    current_topic_context = "main"
    selected_branch_context = ""
    clear_options_frame()

    main_options = [
        "About Us",
        "Courses",
        "Admission",
        "Fees",
        "Scholarships",
        "Hostel",
        "Library",
        "Canteen",
        "Sports & Events",
        "Contact Us",
    ]
    for opt in main_options:
        btn = create_styled_button(
            opt_frame, opt, lambda o=opt: send(o), type_flag="primary"
        )
        btn.pack(side=LEFT, expand=True, fill="x", padx=2, pady=4)


def show_courses_submenu():
    global current_topic_context
    current_topic_context = "courses"
    clear_options_frame()
    branches = ["Computer", "AI & ML", "Mechanical", "Electrical", "Civil", "EXTC"]

    back_btn = create_styled_button(
        opt_frame, "⬅ Back", show_main_menu, type_flag="secondary"
    )
    back_btn.pack(side=LEFT, padx=4, pady=4)

    for br in branches:
        btn = create_styled_button(
            opt_frame, br, lambda b=br: send(b), type_flag="accent"
        )
        btn.pack(side=LEFT, expand=True, fill="x", padx=2, pady=4)


def show_deep_dive_context():
    clear_options_frame()

    back_btn = create_styled_button(
        opt_frame, "⬅ Branches", show_courses_submenu, type_flag="secondary"
    )
    back_btn.pack(side=LEFT, padx=4, pady=4)

    deep_options = ["Syllabus", "Placements", "Eligibility"]
    for option in deep_options:
        btn = create_styled_button(
            opt_frame, option, lambda o=option: send(o), type_flag="primary"
        )
        btn.pack(side=LEFT, expand=True, fill="x", padx=4, pady=4)


# ==========================================
# WINDOW INTERFACE APPLICATION RUNNER
# ==========================================
root = Tk()
root.title("AI College Enquiry Assistant")
root.geometry("880x850")
root.configure(bg="#F1F5F9")

header = Frame(root, bg="#0F766E", height=85)
header.pack(fill="x", side=TOP)
header.pack_propagate(False)

btn_theme = Button(
    header,
    text="🌙 Dark Mode",
    font=("Segoe UI", 9, "bold"),
    bg="#115E59",
    fg="white",
    bd=0,
    cursor="hand2",
    padx=10,
    pady=4,
    command=toggle_theme,
)
btn_theme.place(x=15, y=25)

btn_export = Button(
    header,
    text="📥 Export Chat",
    font=("Segoe UI", 9, "bold"),
    bg="#115E59",
    fg="white",
    bd=0,
    cursor="hand2",
    padx=10,
    pady=4,
    command=export_chat,
)
btn_export.place(x=760, y=25)

Label(
    header,
    text="🎓 B.L.Patil Polytechnic Helpdesk Portal",
    font=("Segoe UI", 16, "bold"),
    bg="#0F766E",
    fg="#FFFFFF",
).pack(pady=(15, 0))
Label(
    header,
    text="Predictive Smart Search Engine Enabled",
    font=("Segoe UI", 9, "normal"),
    bg="#0F766E",
    fg="#CCFBF1",
).pack()

canvas_frame = Frame(root, bg="#F1F5F9")
canvas_frame.pack(fill=BOTH, expand=True, padx=16, pady=10)

canvas = Canvas(canvas_frame, bg="#F1F5F9", highlightthickness=0)
scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
scrollable_frame = Frame(canvas, bg="#F1F5F9")

scrollable_frame.bind(
    "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)
canvas_window = canvas.create_window(
    (0, 0), window=scrollable_frame, anchor="nw", width=810
)

canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))


def _on_mousewheel(event):
    if event.num == 4:
        canvas.yview_scroll(-1, "units")
    elif event.num == 5:
        canvas.yview_scroll(1, "units")
    else:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


canvas.bind_all("<MouseWheel>", _on_mousewheel)
canvas.bind_all("<Button-4>", _on_mousewheel)
canvas.bind_all("<Button-5>", _on_mousewheel)

canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

add_bubble(
    "🤖 Welcome to B.L.Patil Polytechnic Helpdesk! How can I assist you today?",
    is_user=False,
)

opt_label = Label(
    root,
    text="Quick Actions Panel",
    font=("Segoe UI", 9, "bold"),
    bg="#F1F5F9",
    fg="#64748B",
)
opt_label.pack(anchor="w", padx=24, pady=(5, 0))

opt_frame = Frame(root, bg="#F1F5F9")
opt_frame.pack(fill="x", padx=20, pady=(0, 5))
show_main_menu()

bottom = Frame(root, bg="#F1F5F9")
bottom.pack(fill="x", padx=20, pady=(10, 20))

btn_mic = Button(
    bottom,
    text="🎤 Mic",
    font=("Segoe UI", 10, "bold"),
    bg="#0284C7",
    fg="white",
    activebackground="#0369A1",
    activeforeground="white",
    relief="flat",
    width=8,
    command=listen_mic,
    cursor="hand2",
    bd=0,
)
btn_mic.pack(side=LEFT, padx=(0, 8), ipady=8)

entry_container = Frame(bottom, bg="#CBD5E1", bd=1)
entry_container.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12))

entry = Entry(
    entry_container,
    font=("Segoe UI", 12),
    bg="white",
    bd=0,
    insertbackground="#0F766E",
)
entry.pack(fill=BOTH, expand=True, ipady=10, padx=10)

entry.bind("<KeyRelease>", check_key_release)
entry.bind("<Return>", lambda e: send())
entry.focus_set()

prediction_box = Listbox(
    root,
    font=("Segoe UI", 11),
    bg="#FFFFFF",
    fg="#1E293B",
    selectbackground="#E2F1E7",
    selectforeground="#0F766E",
    relief="solid",
    bd=1,
    highlightthickness=0,
)
prediction_box.bind("<<ListboxSelect>>", on_prediction_select)

btn_send = Button(
    bottom,
    text="Send",
    font=("Segoe UI", 10, "bold"),
    bg="#0F766E",
    fg="white",
    activebackground="#115E59",
    activeforeground="white",
    relief="flat",
    width=10,
    command=send,
    cursor="hand2",
    bd=0,
)
btn_send.pack(side=LEFT, padx=2, ipady=8)

btn_clear = Button(
    bottom,
    text="Reset",
    font=("Segoe UI", 10, "bold"),
    bg="#94A3B8",
    fg="white",
    activebackground="#64748B",
    activeforeground="white",
    relief="flat",
    width=8,
    command=clear_chat,
    cursor="hand2",
    bd=0,
)
btn_clear.pack(side=LEFT, padx=2, ipady=8)

if __name__ == "__main__":
    root.mainloop()