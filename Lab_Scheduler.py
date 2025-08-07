# app.py
import streamlit as st
from collections import defaultdict
import random
import time

st.set_page_config(page_title="Constraint Satisfaction Lab Scheduler for Data Science Courses", layout="wide")

# Insert logo
#st.image("https://i.postimg.cc/QdPGCy0z/usiu-logo.png", use_container_width=True)

#st.title("Constraint Satisfaction Lab Scheduler for Data Science Courses")

st.markdown(
    """
    <div style="text-align: center;">
        <img src="https://i.postimg.cc/QdPGCy0z/usiu-logo.png" width="230"/>
        <h3>Constraint Satisfaction Lab Scheduler for Data Science Courses</h3>
    </div>
    """,
    unsafe_allow_html=True
)


# ---------------- User inputs ----------------
st.sidebar.header("Inputs to run the scheduler with customized parameters")

# Course list input (user may paste or keep default)
default_courses = """APT1050_A,APT1050_B,APT1050_C,APT2060_A,APT2060_B,
APT3040_A,APT3040_B,DSA1060_A,DSA1060_B,DSA1080_A,DSA1080_B,DSA2020_A,DSA2040_A,
DSA3020_A,DSA3020_B,DSA3030_A,DSA3050_A,DSA3900_A,DSA4020_A,DSA4030_A,DSA4050_A,
DSA4900_A,DSA4910_A,DSA4000_A,IST1020_A,IST1020_B,IST1020_C,MTH1040_A,MTH1040_B,
MTH1050_A,MTH1050_B,MTH1050_C,MTH1060_A,MTH1060_B,MTH1109_A,MTH1109_B,MTH1110_A,
MTH1110_B,MTH1110_C,MTH2020_A,MTH2020_B,MTH2030_A,MTH2030_B,MTH2215_A,MTH2215_B,
MTH2215_C,MTH3010_A,MTH3010_B,STA1020_A,STA1040_A,STA2010_A,STA2010_B,STA2030_A,
STA2050_A,STA2050_B,STA2060_A,STA3010_A,STA3020_A,STA3040_A,STA3040_B,STA3050_A,
STA4010_A,STA4020_A,STA4030_A,STA4030_B"""
courses_input = st.sidebar.text_area("Course codes (comma-separated)", value=default_courses, height=160)
courses = [c.strip() for c in courses_input.replace("\n",",").split(",") if c.strip()]

# Departments for lecturer inputs
dept_codes = ['STA', 'DSA', 'MTH', 'APT', 'IST']
st.sidebar.markdown("Enter lecturers per department (comma-separated). If left blank, placeholder lecturers will be used.")
user_lecturers = {}
for dept in dept_codes:
    val = st.sidebar.text_input(f"Lecturers for {dept}", "")
    if val.strip():
        user_lecturers[dept] = [x.strip() for x in val.split(",") if x.strip()]

# Number of labs and back-to-back limit
num_labs = st.sidebar.number_input("Number of labs", min_value=1, max_value=20, value=5)
max_back_to_back = st.sidebar.slider("Max consecutive slots per lecturer (back-to-back)", min_value=1, max_value=5, value=2)

# Option: shuffle domain ordering to add randomness 
shuffle_domains = st.sidebar.checkbox("Shuffle each course domain before solve", value=False)

# Slots & defaults (same as your original)
slots_by_day = {
    "Mon": ['7:00–8:40', '9:00–10:40', '11:00–12:40', '1:20–3:00', '3:30–5:10', '5:30–7:10', '7:30–9:00'],
    "Tue": ['7:00–8:40', '9:00–10:40', '11:00–12:40', '1:20–3:00', '3:30–5:10', '5:30–7:10', '7:30–9:00'],
    "Wed": ['7:00–8:40', '9:00–10:40', '11:00–12:40', '1:20–3:00', '3:30–5:10', '5:30–7:10', '7:30–9:00'],
    "Thu": ['7:00–8:40', '9:00–10:40', '11:00–12:40', '1:20–3:00', '3:30–5:10', '5:30–7:10', '7:30–9:00'],
    "Fri": ['8:00–11:20', '1:20–4:40', '5:40–9:00'],
    "Sat": ['9:00–12:20', '1:20–4:40']
}
labs = list(range(1, num_labs + 1))

# If user didn't supply lecturers for a dept, generate anonymized placeholders
placeholders = {
    'STA': [f"STA_Lec{i+1}" for i in range(8)],
    'DSA': [f"DSA_Lec{i+1}" for i in range(10)],
    'MTH': [f"MTH_Lec{i+1}" for i in range(15)],
    'APT': [f"APT_Lec{i+1}" for i in range(9)],
    'IST': [f"IST_Lec{i+1}" for i in range(7)]
}
for d in dept_codes:
    if d not in user_lecturers or not user_lecturers[d]:
        user_lecturers[d] = placeholders[d][:]  # copy

# ---------------- Helpers / Constraints (aligned with your first solver) ----------------
def get_lecturers(course):
    return user_lecturers.get(course[:3], ['Unknown'])

def day_pattern(day):
    if day in ("Mon", "Wed"):
        return "MW"
    if day in ("Tue", "Thu"):
        return "TTh"
    if day in ("Fri", "Sat"):
        return "FriSat"
    return "Other"

def paired_day_of(day):
    """Return the paired day for symmetric pairing (Mon<->Wed, Tue<->Thu)."""
    if day == "Mon": return "Wed"
    if day == "Wed": return "Mon"
    if day == "Tue": return "Thu"
    if day == "Thu": return "Tue"
    return None  # Fri/Sat have no pair

def build_domain_for_course(course):
    lec_list = get_lecturers(course)
    domain = []
    for day in slots_by_day:
        for time in slots_by_day[day]:
            for lab in labs:
                for lec in lec_list:
                    domain.append((day, time, lab, lec))
    return domain

def room_conflict(candidate, room_schedule):
    return (candidate[0], candidate[1], candidate[2]) in room_schedule

def lecturer_conflict(candidate, lec_time_set):
    return (candidate[0], candidate[1], candidate[3]) in lec_time_set

def back_to_back_ok(candidate, lec_schedule, max_back_to_back_local):
    day, time, _, lec = candidate
    if day not in lec_schedule.get(lec, {}):
        return True
    slot_index = {t:i for i,t in enumerate(slots_by_day[day])}
    if time not in slot_index:
        return False
    this_idx = slot_index[time]
    existing = sorted(lec_schedule[lec][day] + [this_idx])
    count = 1
    for i in range(1, len(existing)):
        if existing[i] == existing[i-1] + 1:
            count += 1
            if count > max_back_to_back_local:
                return False
        else:
            count = 1
    return True

def same_course_consistency(candidate, course, assignments):
    """
    Enforce same-course consistency across assigned sessions for that course:
    - Disallow identical day/time/lab.
    - Disallow mixing MW <-> TTh patterns.
    - Disallow mixing FriSat with MW/TTh.
    """
    cand_day, cand_time, cand_lab, cand_lec = candidate
    cand_pat = day_pattern(cand_day)
    for key, val in assignments.items():
        base = key.split("::")[0]
        if base != course:
            continue
        od, ot, ol, olect = val
        # exact day/time/lab duplication not allowed
        if od == cand_day and ot == cand_time and ol == cand_lab:
            return False
        p_other = day_pattern(od)
        if (p_other == "MW" and cand_pat == "TTh") or (p_other == "TTh" and cand_pat == "MW"):
            return False
        if (p_other == "FriSat" and cand_pat in ("MW", "TTh")) or (cand_pat == "FriSat" and p_other in ("MW", "TTh")):
            return False
    return True

# ---------------- Backtracking with pairing and full constraint checks ----------------
def backtrack_assign(index, order, domains, assignments, room_schedule, lec_time_set, lec_schedule, slot_index_map):
    if index >= len(order):
        return True

    course = order[index]
    # iterate domain (optionally shuffle)
    domain = domains[course]
    for cand in domain:
        # primary checks for candidate
        if room_conflict(cand, room_schedule): continue
        if lecturer_conflict(cand, lec_time_set): continue
        if not back_to_back_ok(cand, lec_schedule, max_back_to_back): continue
        if not same_course_consistency(cand, course, assignments): continue

        # if day has a pairing, create pair tuple and check availability
        pday = paired_day_of(cand[0])
        pair = None
        if pday:
            pair = (pday, cand[1], cand[2], cand[3])
            # check pair as well
            if room_conflict(pair, room_schedule): continue
            if lecturer_conflict(pair, lec_time_set): continue
            if not back_to_back_ok(pair, lec_schedule, max_back_to_back): continue
            if not same_course_consistency(pair, course, assignments): continue

        # commit main assignment
        assignments[course] = cand
        room_schedule.add((cand[0], cand[1], cand[2]))
        lec_time_set.add((cand[0], cand[1], cand[3]))
        lec_schedule[cand[3]][cand[0]].append(slot_index_map[cand[0]][cand[1]])

        dup_key = None
        if pair:
            dup_key = course + "::Dup"
            assignments[dup_key] = pair
            room_schedule.add((pair[0], pair[1], pair[2]))
            lec_time_set.add((pair[0], pair[1], pair[3]))
            lec_schedule[pair[3]][pair[0]].append(slot_index_map[pair[0]][pair[1]])

        # recurse
        if backtrack_assign(index + 1, order, domains, assignments, room_schedule, lec_time_set, lec_schedule, slot_index_map):
            return True

        # undo
        assignments.pop(course, None)
        room_schedule.remove((cand[0], cand[1], cand[2]))
        lec_time_set.remove((cand[0], cand[1], cand[3]))
        lec_schedule[cand[3]][cand[0]].pop()
        if dup_key:
            assignments.pop(dup_key, None)
            room_schedule.remove((pair[0], pair[1], pair[2]))
            lec_time_set.remove((pair[0], pair[1], pair[3]))
            lec_schedule[pair[3]][pair[0]].pop()

    return False

def solve_backtracking_paired(user_courses, domains):
    # order vars by smallest domain (fail-first)
    order = sorted(user_courses, key=lambda x: len(domains[x]))
    # optionally shuffle order slightly to help randomness
    # order = sorted(user_courses, key=lambda x: (len(domains[x]), random.random()))

    assignments = {}
    room_schedule = set()
    lec_time_set = set()
    lec_schedule = defaultdict(lambda: defaultdict(list))
    slot_index_map = {day: {t:i for i,t in enumerate(slots_by_day[day])} for day in slots_by_day}

    ok = backtrack_assign(0, order, domains, assignments, room_schedule, lec_time_set, lec_schedule, slot_index_map)
    if not ok:
        return None

    # Group course assignments (main + ::Dup) for display
    course_assignments = defaultdict(list)
    for k, v in assignments.items():
        if k.endswith("::Dup"):
            base = k.split("::")[0]
            course_assignments[base].append((k, v))
        else:
            course_assignments[k].append((k, v))
    return course_assignments

# ---------------- UI Run button ----------------
if st.button("Run scheduler"):
    st.info("Building domains...")
    domains = {}
    for c in courses:
        d = build_domain_for_course(c)
        if shuffle_domains:
            random.shuffle(d)
        domains[c] = d

    st.info("Solving...")
    t0 = time.time()
    sol = solve_backtracking_paired(courses, domains)
    t1 = time.time()

    if not sol:
        st.error(f"No feasible schedule found (search finished in {t1 - t0:.1f}s). Try adding more lecturers or labs, or reduce course list.")
        # store None so search knows there is no schedule
        st.session_state["schedule_map"] = None
    else:
        st.success(f"Schedule found in {t1 - t0:.1f}s")
        rows = []
        schedule_map = {}  # build a mapping course -> {"main": main, "dup": dup}
        for course in sorted(sol):
            main = None
            dup = None
            for k, val in sol[course]:
                if k.endswith("::Dup"):
                    dup = val
                else:
                    main = val
            # Build display row and also save both main and dup (dup may be None)
            if main and dup:
                days = sorted([main[0], dup[0]], key=lambda x: ["Mon","Tue","Wed","Thu","Fri","Sat"].index(x))
                day_str = f"{days[0]}/{days[1]}"
                rows.append({"Course": course, "Day": day_str, "Time": main[1], "Lab": main[2], "Lecturer": main[3]})
                schedule_map[course] = {"main": main, "dup": dup}
            elif main:
                rows.append({"Course": course, "Day": main[0], "Time": main[1], "Lab": main[2], "Lecturer": main[3]})
                schedule_map[course] = {"main": main, "dup": None}
            elif dup:
                rows.append({"Course": course, "Day": dup[0], "Time": dup[1], "Lab": dup[2], "Lecturer": dup[3]})
                schedule_map[course] = {"main": None, "dup": dup}

        # persist the mapping in session_state so search works later without re-running solver
        st.session_state["schedule_map"] = schedule_map

        import pandas as pd
        df = pd.DataFrame(rows)
        df = df.sort_values(["Day", "Time", "Course"])
        st.dataframe(df, use_container_width=True)

        st.markdown("### Summary by day")
        byday = df.groupby("Day").size().rename("Count").reset_index()
        st.table(byday)

        st.download_button("Download CSV", df.to_csv(index=False), file_name="schedule.csv", mime="text/csv")

# === 🔍 Search Section (reads from st.session_state["schedule_map"]) ===
st.subheader("🔍 Search for a Course")
search_input = st.text_input("Enter Course Code (e.g. DSA1080_A):")

# get the persisted schedule map (or None)
schedule = st.session_state.get("schedule_map", None)

if search_input:
    search_input = search_input.strip().upper()
    if schedule and search_input in schedule:
        entry = schedule[search_input]
        main = entry.get("main")
        dup = entry.get("dup")
        # determine day string
        if main and dup:
            day_str = f"{main[0]}/{dup[0]}"
            time_str = main[1]
            lab_str = main[2]
            lec_str = main[3]
        elif main:
            paired = paired_day_of(main[0])
            if paired:
                day_str = f"{main[0]}/{paired}"
            else:
                day_str = main[0]
            time_str = main[1]
            lab_str = main[2]
            lec_str = main[3]
        elif dup:
            paired = paired_day_of(dup[0])
            if paired:
                day_str = f"{dup[0]}/{paired}"
            else:
                day_str = dup[0]
            time_str = dup[1]
            lab_str = dup[2]
            lec_str = dup[3]
        else:
            day_str = "Unknown"
            time_str = ""
            lab_str = ""
            lec_str = ""

        st.success(f"Course found: {search_input}")
        st.write(f"Day(s): {day_str}")
        st.write(f"Time: {time_str}")
        st.write(f"Lab: {lab_str}")
        st.write(f"Lecturer: {lec_str}")
    else:
        st.warning("Course not found in the generated timetable.")

# optional: helpful message when no run has been done yet
if schedule is None:
    st.info("No schedule stored yet. Run the scheduler to generate a timetable, then search for courses.")
