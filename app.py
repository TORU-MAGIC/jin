import streamlit as st
import random
from enum import Enum

st.set_page_config(page_title="🐺 人狼ゲーム", page_icon="🐺", layout="centered")

st.markdown("""
<style>
[data-testid="stApp"] {
    background: linear-gradient(180deg, #0d0d1a 0%, #16213e 100%);
    min-height: 100vh;
}
[data-testid="stAppViewContainer"] { background: transparent; }
.stButton > button {
    background: linear-gradient(135deg, #6b21a8, #4338ca);
    color: white !important;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.5rem;
    font-size: 1rem;
    font-weight: 600;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }
.stSelectbox label, .stNumberInput label, .stTextInput label { color: #94a3b8 !important; }
div[data-testid="stMetricValue"] { color: white !important; }
div[data-testid="stMetricLabel"] { color: #94a3b8 !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: white; }
p { color: #e2e8f0; }
.card {
    background: rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 1.5rem;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 1rem;
}
.card-wolf {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.4);
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.card-village {
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.4);
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.card-night {
    background: rgba(99,102,241,0.1);
    border: 1px solid rgba(99,102,241,0.4);
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.card-day {
    background: rgba(251,191,36,0.1);
    border: 1px solid rgba(251,191,36,0.4);
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.player-chip {
    display: inline-block;
    background: rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 0.3rem 0.8rem;
    margin: 0.2rem;
    color: white;
    font-size: 0.9rem;
}
.dead-chip {
    display: inline-block;
    background: rgba(239,68,68,0.15);
    border-radius: 20px;
    padding: 0.3rem 0.8rem;
    margin: 0.2rem;
    color: #f87171;
    font-size: 0.9rem;
    text-decoration: line-through;
}
</style>
""", unsafe_allow_html=True)


class Phase(Enum):
    SETUP = "setup"
    ROLE_REVEAL = "role_reveal"
    NIGHT = "night"
    MORNING = "morning"
    DAY = "day"
    VOTE = "vote"
    VOTE_RESULT = "vote_result"
    GAME_OVER = "game_over"


class Role(Enum):
    WEREWOLF = "人狼"
    VILLAGER = "村人"
    SEER = "占い師"
    DOCTOR = "騎士"
    MADMAN = "狂人"


ROLE_INFO = {
    Role.WEREWOLF: {"icon": "🐺", "team": "wolf",    "color": "#ef4444", "desc": "夜に村人を1人襲います。村人チームを全滅させれば人狼チームの勝利！"},
    Role.VILLAGER: {"icon": "👤", "team": "village", "color": "#22c55e", "desc": "特殊な能力はありませんが、昼の議論と投票で人狼を見つけ出しましょう。"},
    Role.SEER:     {"icon": "🔮", "team": "village", "color": "#818cf8", "desc": "夜に1人を選んで人狼かどうかを占えます。情報を上手く使いましょう。"},
    Role.DOCTOR:   {"icon": "💊", "team": "village", "color": "#34d399", "desc": "夜に1人を選んで人狼の攻撃から守れます。誰を守るか見極めが重要。"},
    Role.MADMAN:   {"icon": "🃏", "team": "wolf",    "color": "#f59e0b", "desc": "人狼の仲間ですが、人狼の行動は知りません。人狼チームの勝利を目指します。"},
}

ROLE_CONFIGS = {
    4:  [Role.WEREWOLF, Role.SEER, Role.VILLAGER, Role.VILLAGER],
    5:  [Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.VILLAGER, Role.VILLAGER],
    6:  [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.VILLAGER, Role.VILLAGER],
    7:  [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.MADMAN, Role.VILLAGER, Role.VILLAGER],
    8:  [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.MADMAN, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER],
    9:  [Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.MADMAN, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER],
    10: [Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.DOCTOR, Role.MADMAN, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER],
}


def init_state():
    defaults = {
        "phase": Phase.SETUP,
        "players": {},
        "day": 0,
        "reveal_index": 0,
        "reveal_shown": False,
        "night_step": 0,
        "night_actions": {},
        "seer_history": {},
        "eliminated_last_night": None,
        "votes": {},
        "vote_index": 0,
        "vote_result": None,
        "winner": None,
        "log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def alive_players():
    return [n for n, p in st.session_state.players.items() if p["alive"]]


def get_role_players(role: Role, alive_only=True):
    return [n for n, p in st.session_state.players.items()
            if p["role"] == role and (not alive_only or p["alive"])]


def check_win():
    alive = alive_players()
    wolves = [n for n in alive if st.session_state.players[n]["role"] == Role.WEREWOLF]
    others = [n for n in alive if st.session_state.players[n]["role"] != Role.WEREWOLF]
    if len(wolves) == 0:
        return "village"
    if len(wolves) >= len(others):
        return "wolf"
    return None


def add_log(msg):
    st.session_state.log.append(msg)


def divider():
    st.markdown('<hr style="border-color:rgba(255,255,255,0.1); margin:1.5rem 0;">', unsafe_allow_html=True)


def phase_header(icon, title, subtitle, color="#a78bfa"):
    st.markdown(f"""
    <div style="text-align:center; padding:1.5rem 1rem 0.5rem;">
        <div style="font-size:3rem;">{icon}</div>
        <h1 style="color:{color}; margin:0.3rem 0;">{title}</h1>
        <p style="color:#64748b; margin:0;">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# ===== SETUP =====
def show_setup():
    phase_header("🐺", "人狼ゲーム", "ルールを決めてゲームを開始しましょう")
    divider()

    st.markdown("#### 👥 プレイヤー人数")
    player_count = st.number_input("", min_value=4, max_value=10, value=6, step=1, label_visibility="collapsed")

    st.markdown("#### 📛 プレイヤー名")
    names = []
    cols = st.columns(2)
    for i in range(player_count):
        with cols[i % 2]:
            name = st.text_input(f"プレイヤー {i+1}", value=f"プレイヤー{i+1}", key=f"pname_{i}")
            names.append(name.strip())

    divider()
    st.markdown("#### ⚔️ 役職構成（自動）")
    config = ROLE_CONFIGS.get(player_count, ROLE_CONFIGS[6])
    role_counts = {}
    for r in config:
        role_counts[r] = role_counts.get(r, 0) + 1

    cols = st.columns(len(role_counts))
    for i, (role, count) in enumerate(role_counts.items()):
        info = ROLE_INFO[role]
        with cols[i]:
            st.markdown(f"""
            <div style="text-align:center; padding:0.8rem; background:rgba(255,255,255,0.06); border-radius:10px;">
                <div style="font-size:1.8rem;">{info['icon']}</div>
                <div style="color:{info['color']}; font-weight:700; font-size:1.5rem;">{count}</div>
                <div style="color:#94a3b8; font-size:0.85rem;">{role.value}</div>
            </div>
            """, unsafe_allow_html=True)

    divider()
    if st.button("🎮　ゲームスタート！", use_container_width=True):
        if len(set(names)) != len(names):
            st.error("プレイヤー名が重複しています")
            return
        if any(not n for n in names):
            st.error("名前をすべて入力してください")
            return

        roles = config.copy()
        random.shuffle(roles)
        st.session_state.players = {
            name: {"role": role, "alive": True}
            for name, role in zip(names, roles)
        }
        st.session_state.reveal_index = 0
        st.session_state.reveal_shown = False
        st.session_state.phase = Phase.ROLE_REVEAL
        st.rerun()


# ===== ROLE REVEAL =====
def show_role_reveal():
    player_names = list(st.session_state.players.keys())
    idx = st.session_state.reveal_index

    if idx >= len(player_names):
        st.session_state.phase = Phase.NIGHT
        st.session_state.day = 1
        st.session_state.night_step = 0
        st.session_state.night_actions = {}
        st.rerun()
        return

    current = player_names[idx]
    total = len(player_names)

    st.markdown(f"""
    <div style="text-align:center; color:#475569; font-size:0.9rem; margin-top:1rem;">
        役職確認 {idx + 1} / {total}
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.reveal_shown:
        phase_header("📱", f"{current} さん", "他の人はスクリーンを見ないでください", "#a78bfa")
        divider()
        st.markdown('<div style="text-align:center;">', unsafe_allow_html=True)
        if st.button("🔍　自分の役職を確認する", use_container_width=True):
            st.session_state.reveal_shown = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        role = st.session_state.players[current]["role"]
        info = ROLE_INFO[role]
        team_label = "人狼チーム" if info["team"] == "wolf" else "村人チーム"
        st.markdown(f"""
        <div style="text-align:center; padding:2.5rem 1.5rem; background:rgba(255,255,255,0.05);
                    border-radius:16px; border:2px solid {info['color']}; margin:1rem 0;">
            <p style="color:#64748b; margin:0; font-size:1rem;">{current} さんの役職</p>
            <div style="font-size:5rem; margin:0.8rem 0;">{info['icon']}</div>
            <h1 style="color:{info['color']}; font-size:2.8rem; margin:0;">{role.value}</h1>
            <p style="color:#94a3b8; font-size:0.85rem; margin:0.3rem 0;">【{team_label}】</p>
            <p style="color:#e2e8f0; margin-top:1rem; font-size:0.95rem; line-height:1.6;">{info['desc']}</p>
        </div>
        """, unsafe_allow_html=True)

        label = "次の人へ ▶" if idx < total - 1 else "ゲーム開始 🌙"
        if st.button(label, use_container_width=True):
            st.session_state.reveal_index += 1
            st.session_state.reveal_shown = False
            st.rerun()


# ===== NIGHT =====
def get_night_steps():
    steps = []
    seers = get_role_players(Role.SEER)
    if seers:
        steps.append(("seer", seers[0]))
    doctors = get_role_players(Role.DOCTOR)
    if doctors:
        steps.append(("doctor", doctors[0]))
    wolves = get_role_players(Role.WEREWOLF)
    if wolves:
        steps.append(("wolf", wolves))
    return steps


def show_night():
    phase_header("🌙", f"第 {st.session_state.day} 夜", "村は静まり返っています...", "#60a5fa")
    divider()

    steps = get_night_steps()
    step_idx = st.session_state.night_step

    if step_idx >= len(steps):
        st.markdown("""
        <div class="card-night" style="text-align:center;">
            <h3 style="color:#818cf8;">夜のアクションが完了しました</h3>
            <p style="color:#94a3b8;">朝になるとどうなるでしょうか...</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("☀️　朝になりました", use_container_width=True):
            process_night()
        return

    action_type, actor = steps[step_idx]

    if action_type == "seer":
        night_seer(actor)
    elif action_type == "doctor":
        night_doctor(actor)
    elif action_type == "wolf":
        night_wolf(actor)


def night_pass_screen(name, label, button_text, color, callback_key):
    if not st.session_state.night_actions.get(callback_key):
        st.markdown(f"""
        <div style="text-align:center; padding:2rem; background:rgba(0,0,0,0.3); border-radius:14px; border:1px solid {color};">
            <h3 style="color:{color};">📱 デバイスを渡してください</h3>
            <h2 style="color:white;">{name} さん</h2>
            <p style="color:#94a3b8;">（{label}）</p>
            <p style="color:#475569; font-size:0.9rem;">他の人は目を閉じてください</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button(button_text, use_container_width=True):
            st.session_state.night_actions[callback_key] = True
            st.rerun()
        return False
    return True


def night_seer(seer_name):
    if not night_pass_screen(seer_name, "占い師", "🔮　占いを行う", "#818cf8", "seer_ready"):
        return

    if not st.session_state.night_actions.get("seer_result"):
        targets = [n for n in alive_players() if n != seer_name]
        st.markdown(f"### 🔮 誰を占いますか？")
        target = st.selectbox("占う相手を選んでください", targets, key="seer_sel")
        if st.button("✨　占う", use_container_width=True):
            role = st.session_state.players[target]["role"]
            is_wolf = role == Role.WEREWOLF
            st.session_state.night_actions["seer_result"] = {"target": target, "is_wolf": is_wolf}
            if seer_name not in st.session_state.seer_history:
                st.session_state.seer_history[seer_name] = []
            st.session_state.seer_history[seer_name].append({"target": target, "is_wolf": is_wolf, "day": st.session_state.day})
            st.rerun()
    else:
        r = st.session_state.night_actions["seer_result"]
        color = "#ef4444" if r["is_wolf"] else "#22c55e"
        text = "🐺 人狼です！" if r["is_wolf"] else "✅ 人狼ではありません"
        st.markdown(f"""
        <div style="text-align:center; padding:2rem; border-radius:14px; border:2px solid {color}; background:rgba(0,0,0,0.3);">
            <h3 style="color:#818cf8;">占い結果</h3>
            <h2 style="color:white; margin:0.5rem 0;">{r['target']}</h2>
            <h1 style="color:{color};">{text}</h1>
        </div>
        """, unsafe_allow_html=True)
        if st.button("確認しました ▶", use_container_width=True):
            st.session_state.night_actions.pop("seer_ready", None)
            st.session_state.night_actions.pop("seer_result", None)
            st.session_state.night_step += 1
            st.rerun()


def night_doctor(doctor_name):
    if not night_pass_screen(doctor_name, "騎士", "💊　護衛を行う", "#34d399", "doctor_ready"):
        return

    targets = alive_players()
    st.markdown("### 💊 誰を護衛しますか？")
    target = st.selectbox("守る相手を選んでください", targets, key="doctor_sel")
    if st.button("🛡️　護衛する", use_container_width=True):
        st.session_state.night_actions["doctor_target"] = target
        st.session_state.night_actions.pop("doctor_ready", None)
        st.session_state.night_step += 1
        st.rerun()


def night_wolf(wolf_list):
    wolf_names = "・".join(wolf_list)
    if not night_pass_screen(f"人狼チーム（{wolf_names}）", "人狼", "🐺　襲撃を行う", "#ef4444", "wolf_ready"):
        return

    non_wolves = [n for n in alive_players() if st.session_state.players[n]["role"] != Role.WEREWOLF]
    st.markdown("### 🐺 誰を襲撃しますか？")
    target = st.selectbox("襲撃する相手を選んでください", non_wolves, key="wolf_sel")
    if st.button("⚔️　襲撃する", use_container_width=True):
        st.session_state.night_actions["wolf_target"] = target
        st.session_state.night_actions.pop("wolf_ready", None)
        st.session_state.night_step += 1
        st.rerun()


def process_night():
    wolf_target = st.session_state.night_actions.get("wolf_target")
    doctor_target = st.session_state.night_actions.get("doctor_target")

    if wolf_target and wolf_target != doctor_target:
        st.session_state.players[wolf_target]["alive"] = False
        st.session_state.eliminated_last_night = wolf_target
        add_log(f"第{st.session_state.day}夜: {wolf_target} が人狼に襲われました")
    else:
        if wolf_target and wolf_target == doctor_target:
            add_log(f"第{st.session_state.day}夜: 騎士が {wolf_target} を護衛しました！")
        st.session_state.eliminated_last_night = None

    st.session_state.night_actions = {}
    st.session_state.night_step = 0

    winner = check_win()
    if winner:
        st.session_state.winner = winner
        st.session_state.phase = Phase.GAME_OVER
    else:
        st.session_state.phase = Phase.DAY
        st.session_state.votes = {}
        st.session_state.vote_index = 0
        st.session_state.vote_result = None
    st.rerun()


# ===== DAY =====
def show_day():
    phase_header("☀️", f"第 {st.session_state.day} 日", "村人たちが目を覚ましました", "#fbbf24")
    divider()

    eliminated = st.session_state.eliminated_last_night
    if eliminated:
        role = st.session_state.players[eliminated]["role"]
        info = ROLE_INFO[role]
        st.markdown(f"""
        <div class="card-wolf" style="text-align:center;">
            <h3 style="color:#f87171; margin:0;">😢 昨夜の犠牲者</h3>
            <h2 style="color:white; margin:0.5rem 0;">{eliminated}</h2>
            <p style="color:#94a3b8; margin:0;">{info['icon']} {role.value}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="card-village" style="text-align:center;">
            <h3 style="color:#4ade80; margin:0;">✨ 昨夜は誰も犠牲になりませんでした！</h3>
        </div>
        """, unsafe_allow_html=True)

    divider()
    st.markdown("#### 🧑 生存者")
    alive = alive_players()
    chips = "".join(f'<span class="player-chip">{n}</span>' for n in alive)
    st.markdown(f'<div style="margin-bottom:1rem;">{chips}</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="text-align:center;">
        <p style="color:#94a3b8; margin:0; font-size:0.95rem;">💬 議論の時間です。怪しい人狼を話し合いで見つけましょう！<br>
        準備ができたら投票に進んでください。</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🗳️　投票へ進む", use_container_width=True):
        st.session_state.phase = Phase.VOTE
        st.session_state.votes = {}
        st.session_state.vote_index = 0
        st.session_state.vote_result = None
        st.rerun()


# ===== VOTE =====
def show_vote():
    alive = alive_players()
    vote_idx = st.session_state.vote_index

    if vote_idx >= len(alive):
        if not st.session_state.vote_result:
            tally = {}
            for target in st.session_state.votes.values():
                tally[target] = tally.get(target, 0) + 1
            max_v = max(tally.values()) if tally else 0
            top = [n for n, c in tally.items() if c == max_v]
            executed = random.choice(top)
            st.session_state.players[executed]["alive"] = False
            role = st.session_state.players[executed]["role"]
            add_log(f"第{st.session_state.day}日: {executed}（{role.value}）が処刑されました")
            st.session_state.vote_result = {"executed": executed, "tally": tally}
            winner = check_win()
            if winner:
                st.session_state.winner = winner
        show_vote_result()
        return

    voter = alive[vote_idx]
    phase_header("🗳️", f"第 {st.session_state.day} 日 投票", f"{vote_idx + 1} / {len(alive)} 人目", "#fbbf24")
    divider()

    st.markdown(f"""
    <div class="card-day" style="text-align:center;">
        <h3 style="color:#fbbf24; margin:0;">📱 デバイスを渡してください</h3>
        <h2 style="color:white; margin:0.5rem 0;">{voter} さんが投票します</h2>
        <p style="color:#64748b; margin:0; font-size:0.9rem;">誰を処刑しますか？</p>
    </div>
    """, unsafe_allow_html=True)

    targets = [n for n in alive if n != voter]
    target = st.selectbox("処刑する人を選んでください", targets, key=f"vote_{vote_idx}")
    if st.button("🗳️　投票する", use_container_width=True):
        st.session_state.votes[voter] = target
        st.session_state.vote_index += 1
        st.rerun()


def show_vote_result():
    r = st.session_state.vote_result
    executed = r["executed"]
    tally = r["tally"]
    role = st.session_state.players[executed]["role"]
    info = ROLE_INFO[role]

    phase_header("⚖️", "投票結果", "多数決で処刑が決まりました", "#f87171")
    divider()

    st.markdown("#### 📊 得票数")
    total_votes = len(st.session_state.votes)
    for name, count in sorted(tally.items(), key=lambda x: -x[1]):
        pct = int(count / total_votes * 20)
        bar = "█" * pct + "░" * (20 - pct)
        color = "#ef4444" if name == executed else "#94a3b8"
        st.markdown(f'<p style="color:{color}; font-family:monospace;">{name}：{bar} {count}票</p>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="card-wolf" style="text-align:center; margin-top:1rem;">
        <h3 style="color:#f87171; margin:0;">⚖️ 処刑</h3>
        <h2 style="color:white; margin:0.5rem 0;">{executed}</h2>
        <p style="color:#94a3b8; margin:0;">{info['icon']} {role.value}</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.winner:
        if st.button("🏆　ゲーム結果を見る", use_container_width=True):
            st.session_state.phase = Phase.GAME_OVER
            st.rerun()
    else:
        if st.button("🌙　夜に進む", use_container_width=True):
            st.session_state.day += 1
            st.session_state.eliminated_last_night = None
            st.session_state.phase = Phase.NIGHT
            st.rerun()


# ===== GAME OVER =====
def show_game_over():
    winner = st.session_state.winner
    if winner == "village":
        phase_header("🎉", "村人チームの勝利！", "すべての人狼を倒しました", "#4ade80")
        win_color = "#22c55e"
    else:
        phase_header("🐺", "人狼チームの勝利！", "人狼が村を支配しました...", "#f87171")
        win_color = "#ef4444"

    divider()
    st.markdown("#### 📋 全員の役職")
    for name, data in st.session_state.players.items():
        role = data["role"]
        info = ROLE_INFO[role]
        alive_text = "✅ 生存" if data["alive"] else "💀 死亡"
        color = info["color"]
        st.markdown(f"""
        <div style="display:flex; align-items:center; padding:0.6rem 1rem;
                    background:rgba(255,255,255,0.04); border-radius:10px; margin:0.3rem 0;
                    border-left:4px solid {color};">
            <span style="font-size:1.4rem; margin-right:0.8rem;">{info['icon']}</span>
            <span style="color:white; flex:1; font-weight:500;">{name}</span>
            <span style="color:{color}; margin-right:1rem; font-size:0.9rem;">{role.value}</span>
            <span style="color:#475569; font-size:0.85rem;">{alive_text}</span>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.log:
        divider()
        with st.expander("📜 ゲームログを見る"):
            for entry in st.session_state.log:
                st.markdown(f"- {entry}")

    divider()
    if st.button("🔄　もう一度プレイする", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ===== MAIN =====
init_state()

phase = st.session_state.phase
if phase == Phase.SETUP:
    show_setup()
elif phase == Phase.ROLE_REVEAL:
    show_role_reveal()
elif phase == Phase.NIGHT:
    show_night()
elif phase == Phase.DAY:
    show_day()
elif phase == Phase.VOTE:
    show_vote()
elif phase == Phase.GAME_OVER:
    show_game_over()
