try:
    import websockets
except ImportError:
    websockets = None

import asyncio, json, random, socket

CONFIGS = {
    4:  ['WEREWOLF','SEER','VILLAGER','VILLAGER'],
    5:  ['WEREWOLF','SEER','DOCTOR','VILLAGER','VILLAGER'],
    6:  ['WEREWOLF','WEREWOLF','SEER','DOCTOR','VILLAGER','VILLAGER'],
    7:  ['WEREWOLF','WEREWOLF','SEER','DOCTOR','MADMAN','VILLAGER','VILLAGER'],
    8:  ['WEREWOLF','WEREWOLF','SEER','DOCTOR','MADMAN','VILLAGER','VILLAGER','VILLAGER'],
    9:  ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','MADMAN','VILLAGER','VILLAGER'],
    10: ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','MADMAN','VILLAGER','VILLAGER','VILLAGER'],
    11: ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER'],
    12: ['WEREWOLF','WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER'],
    13: ['WEREWOLF','WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER','VILLAGER'],
    14: ['WEREWOLF','WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER'],
    15: ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','SHARED','SHARED','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER'],
    16: ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','SHARED','SHARED','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER'],
    17: ['WEREWOLF','WEREWOLF','WEREWOLF','SEER','DOCTOR','MEDIUM','SHARED','SHARED','NEKOMATA','MADMAN','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER','VILLAGER'],
}
MAX_PLAYERS = 17
CPU_NAMES = ['ボブ','井沢','工場長','狩野英孝','マリック','キングカズ','カズレーザー','リンゴちゃん','柳沢','沢枝','イッコー','マツコ','アンジャッシュ渡部','ピコ太郎','ハル','ユキ']
CHARACTER_COUNT = 16
DISC_ROUNDS = 2
READ_PAUSE_MIN = 1.4
READ_PAUSE_MAX = 7.0

def read_pause(text):
    length = len(text or '')
    return max(READ_PAUSE_MIN, min(READ_PAUSE_MAX, 1.0 + length * 0.075))

# CPU テンプレート
CPU_T = {
    'neutral': [
        '様子を見ています',
        '情報が少なくて判断できません',
        'みんなの意見を聞かせてください',
        '焦らず冷静に考えましょう',
        '昨夜は特に気になることはありませんでした',
    ],
    'accuse': [
        '{t}さんが少し怪しいと思います',
        '{t}さんの言動が気になります',
        '{t}さんへの投票を考えています',
        '{t}さん、説明してもらえますか？',
        '{t}さんは人狼じゃないですか？',
    ],
    'defend': [
        '私は村人です！信じてください',
        '私は人狼ではありません',
        'なぜ私を疑うのですか？',
        '違います！私は無実です',
        '私を信じてください',
    ],
    'agree': [
        '{t}さんへの疑惑、私も同感です',
        '確かに{t}さんが気になりますね',
        '{t}さんを今日は処刑すべきでは？',
    ],
    'wolf_bluff': [
        '私は絶対に村人です！',
        '早く人狼を見つけましょう',
        '村人同士で協力しましょう',
    ],
    'wolf_accuse': [
        '{t}さんが怪しいと感じています',
        '{t}さんを今日は処刑すべきでは？',
    ],
    'wolf_chat': [
        '今夜は{t}さんを狙いましょう',
        '{t}さんを先に消したい',
        '了解！{t}さんにしよう',
        '同意します',
        '{t}さんで決まりですね',
    ],
}

rooms = {}

def gen_code():
    while True:
        c = str(random.randint(0, 999)).zfill(3)
        if c not in rooms: return c

def normalize_code(value):
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return digits[:3].zfill(3) if digits else ''

def new_room(code):
    return {
        'code': code, 'players': {}, 'host': None,
        'phase': 'lobby', 'day': 0, 'cpu_pids': set(),
        'disc_msgs': [], 'disc_order': [], 'disc_step': 0, 'disc_round': 0,
        'wolf_chat': [], 'wolf_done': set(),
        'night_actions': {}, 'night_pending': set(),
        'last_doctor_target': None,
        'last_executed': None, 'last_executed_role': None,
        'votes': {}, 'vote_reasons': {}, 'vote_pending': set(), 'log': [],
        'vote_ready': set(),
        'desired_cpu': 0,
    }

async def bcast(room, msg, skip=None):
    dead = []
    for pid, p in list(room['players'].items()):
        if pid == skip or pid in room['cpu_pids']: continue
        try: await p['ws'].send(json.dumps(msg))
        except: dead.append(pid)
    for pid in dead: room['players'].pop(pid, None)

async def send1(room, pid, msg):
    if pid in room['cpu_pids']: return
    p = room['players'].get(pid)
    if p:
        try: await p['ws'].send(json.dumps(msg))
        except: pass

def alive(room): return {pid: p for pid, p in room['players'].items() if p['alive']}
def wolf_list(room): return [pid for pid, p in room['players'].items() if p['role'] == 'WEREWOLF' and p['alive']]

def check_win(room):
    a = alive(room)
    w = sum(1 for p in a.values() if p['role'] == 'WEREWOLF')
    o = len(a) - w
    if w == 0: return 'village'
    if w >= o: return 'wolf'
    return None

def public_player(room, pid, p, include_role=False):
    data = {
        'name': p['name'],
        'alive': p['alive'],
        'is_cpu': pid in room['cpu_pids'],
        'isCpu': pid in room['cpu_pids'],
        'avatarIndex': p.get('avatarIndex'),
    }
    if include_role:
        data['role'] = p.get('role')
    return data

def plist(room):
    return [public_player(room, pid, p) for pid, p in room['players'].items()]

def assign_avatar_indexes(room):
    order = list(range(CHARACTER_COUNT))
    random.shuffle(order)
    used = set()
    name_to_idx = {name: i % CHARACTER_COUNT for i, name in enumerate(CPU_NAMES)}

    def next_idx():
        for idx in order:
            if idx not in used:
                used.add(idx)
                return idx
        idx = random.randrange(CHARACTER_COUNT)
        used.add(idx)
        return idx

    for _, p in room['players'].items():
        preferred = name_to_idx.get(p.get('name'))
        if preferred is not None and preferred not in used:
            p['avatarIndex'] = preferred
            used.add(preferred)
        else:
            p['avatarIndex'] = next_idx()

# ── CPU ロジック ──────────────────────────────────────────────
def cpu_template(room, cpu_pid, ctx='discuss'):
    p = room['players'][cpu_pid]
    role = p['role']
    wolf_set = {pid for pid, q in room['players'].items() if q['role'] == 'WEREWOLF'}
    alive_others = [(pid, q) for pid, q in room['players'].items() if q['alive'] and pid != cpu_pid]

    if ctx == 'wolf_chat':
        non_wolves = [q for pid, q in room['players'].items() if q['alive'] and pid not in wolf_set]
        if non_wolves:
            t = random.choice(non_wolves)['name']
            return random.choice(CPU_T['wolf_chat']).replace('{t}', t)
        return '同意します'

    # 直近の議論から疑われ状況を分析
    recent = room['disc_msgs'][-6:]
    accused = {}
    for m in recent:
        for _, q in alive_others:
            if q['name'] in m['text'] and any(w in m['text'] for w in ['怪しい','疑','投票','処刑']):
                accused[q['name']] = accused.get(q['name'], 0) + 1

    was_accused = p['name'] in accused
    top_accused = max(accused, key=accused.get) if accused else None

    if role in ['WEREWOLF', 'MADMAN']:
        if was_accused:
            return random.choice(CPU_T['defend'])
        non_wolf_alive = [q for pid, q in alive_others if pid not in wolf_set]
        r = random.random()
        if r < 0.35 and non_wolf_alive:
            t = random.choice(non_wolf_alive)['name']
            return random.choice(CPU_T['wolf_accuse']).replace('{t}', t)
        elif r < 0.65:
            return random.choice(CPU_T['wolf_bluff'])
        else:
            return random.choice(CPU_T['neutral'])
    else:
        if was_accused and random.random() < 0.7:
            return random.choice(CPU_T['defend'])
        if top_accused and random.random() < 0.4:
            return random.choice(CPU_T['agree']).replace('{t}', top_accused)
        r = random.random()
        if r < 0.4 and alive_others:
            t = random.choice(alive_others)[1]['name']
            return random.choice(CPU_T['accuse']).replace('{t}', t)
        return random.choice(CPU_T['neutral'])

# ── 人狼チャット ─────────────────────────────────────────────
async def start_wolf_chat(room):
    room['phase'] = 'wolf_chat'
    room['wolf_chat'] = []
    room['wolf_done'] = set()
    wlist = wolf_list(room)
    if len(wlist) < 2:
        await start_night_actions(room); return
    wnames = [room['players'][w]['name'] for w in wlist]
    for wid in wlist:
        await send1(room, wid, {'type': 'wolf_chat_start', 'wolf_names': wnames, 'day': room['day']})
    for wid in wlist:
        if wid in room['cpu_pids']:
            asyncio.create_task(_cpu_wolf_chat(room, wid))

async def _cpu_wolf_chat(room, cpu_pid):
    await asyncio.sleep(random.uniform(0.6, 1.8))
    if room['phase'] != 'wolf_chat': return
    msg = cpu_template(room, cpu_pid, ctx='wolf_chat')
    p = room['players'][cpu_pid]
    room['wolf_chat'].append({'name': p['name'], 'text': msg})
    for wid in wolf_list(room):
        await send1(room, wid, {'type': 'wolf_chat_msg', 'name': p['name'], 'text': msg})
    room['wolf_done'].add(cpu_pid)
    human_wolves = [w for w in wolf_list(room) if w not in room['cpu_pids']]
    if room['wolf_done'].issuperset(set(human_wolves)):
        await start_night_actions(room)

# ── 夜アクション ──────────────────────────────────────────────
async def start_night_actions(room):
    room['phase'] = 'night'
    room['night_actions'] = {}
    room['night_pending'] = set()
    await bcast(room, {'type': 'night_start', 'day': room['day']})

    if room.get('last_executed'):
        for mid, mp in room['players'].items():
            if mp['alive'] and mp['role'] == 'MEDIUM' and mid not in room['cpu_pids']:
                await send1(room, mid, {'type': 'medium_reveal',
                                        'target': room.get('last_executed'),
                                        'role': room.get('last_executed_role')})

    for pid, p in room['players'].items():
        if not p['alive']: continue
        if p['role'] == 'SEER':
            tgts = [{'name': q['name']} for qid, q in room['players'].items() if q['alive'] and qid != pid]
            await send1(room, pid, {'type': 'action_needed', 'action': 'seer', 'targets': tgts})
            room['night_pending'].add(('seer', pid))
            if pid in room['cpu_pids']:
                asyncio.create_task(_cpu_night(room, pid, 'seer', tgts))
        elif p['role'] == 'DOCTOR':
            tgts = [{'name': q['name']} for qid, q in room['players'].items()
                    if q['alive'] and qid != pid and q['name'] != room.get('last_doctor_target')]
            if tgts:
                await send1(room, pid, {'type': 'action_needed', 'action': 'doctor', 'targets': tgts,
                                        'last_protected': room.get('last_doctor_target')})
                room['night_pending'].add(('doctor', pid))
                if pid in room['cpu_pids']:
                    asyncio.create_task(_cpu_night(room, pid, 'doctor', tgts))

    wlist = wolf_list(room)
    if wlist:
        tgts = [{'name': p['name']} for p in room['players'].values() if p['alive'] and p['role'] != 'WEREWOLF']
        wnames = [room['players'][w]['name'] for w in wlist]
        for wid in wlist:
            await send1(room, wid, {'type': 'action_needed', 'action': 'wolf', 'targets': tgts, 'wolf_names': wnames})
        room['night_pending'].add(('wolf', wlist[0]))
        if wlist[0] in room['cpu_pids']:
            asyncio.create_task(_cpu_night(room, wlist[0], 'wolf', tgts))

    if not room['night_pending']:
        await do_morning(room)

async def _cpu_night(room, cpu_pid, action, tgts):
    await asyncio.sleep(random.uniform(0.5, 1.5))
    if not tgts: return
    target = random.choice(tgts)['name']
    await _apply_night_action(room, cpu_pid, action, target)

async def _apply_night_action(room, pid, action, target):
    if action == 'seer':
        actor = room['players'].get(pid)
        target_player = next((p for p in room['players'].values() if p['name'] == target and p['alive']), None)
        if ('seer', pid) not in room['night_pending']:
            return
        if not actor or not actor.get('alive') or actor.get('role') != 'SEER' or not target_player or target_player['name'] == actor['name']:
            await send1(room, pid, {'type': 'error', 'msg': '占える相手を選び直してください'})
            return
        role = target_player['role']
        await send1(room, pid, {'type': 'seer_result', 'target': target, 'is_wolf': role == 'WEREWOLF'})
        room['night_actions']['seer_target'] = target
        room['night_pending'].discard(('seer', pid))
    elif action == 'doctor':
        actor = room['players'].get(pid)
        target_player = next((p for p in room['players'].values() if p['name'] == target and p['alive']), None)
        if ('doctor', pid) not in room['night_pending']:
            return
        if not actor or not actor.get('alive') or actor.get('role') != 'DOCTOR':
            await send1(room, pid, {'type': 'error', 'msg': 'invalid doctor action'})
            return
        if not actor or not target_player or target == actor['name']:
            await send1(room, pid, {'type': 'error', 'msg': '騎士は自分自身を護衛できません'})
            return
        if target == room.get('last_doctor_target'):
            await send1(room, pid, {'type': 'error', 'msg': '同じ人を2夜連続で護衛することはできません'})
            return
        room['night_actions']['doctor_target'] = target
        room['night_pending'].discard(('doctor', pid))
        await send1(room, pid, {'type': 'action_ack', 'action': 'doctor'})
    elif action == 'wolf':
        actor = room['players'].get(pid)
        target_player = next((p for p in room['players'].values() if p['name'] == target and p['alive']), None)
        if not any(x[0] == 'wolf' for x in room['night_pending']):
            return
        if not actor or not actor.get('alive') or actor.get('role') != 'WEREWOLF' or not target_player or target_player['role'] == 'WEREWOLF':
            await send1(room, pid, {'type': 'error', 'msg': 'invalid wolf target'})
            return
        if 'wolf_target' not in room['night_actions']:
            room['night_actions']['wolf_target'] = target
            for wid in wolf_list(room):
                await send1(room, wid, {'type': 'wolf_chosen', 'target': target})
            room['night_pending'] = {x for x in room['night_pending'] if x[0] != 'wolf'}
    if not room['night_pending']:
        await do_morning(room)

async def do_morning(room):
    wt = room['night_actions'].get('wolf_target')
    dt = room['night_actions'].get('doctor_target')
    room['last_doctor_target'] = dt
    night_report = {'day': room['day'], 'target': wt, 'protected': dt,
                    'guarded': False, 'victim': None, 'dragged': None}
    elim = None
    if wt and wt != dt:
        for p in room['players'].values():
            if p['name'] == wt and p['alive']:
                p['alive'] = False; elim = {'name': wt, 'role': p['role']}
                night_report['victim'] = wt
                room['log'].append(f"第{room['day']}夜: {wt} が人狼に襲われました")
                if p['role'] == 'NEKOMATA':
                    wolves = [(pid, q) for pid, q in room['players'].items()
                              if q['alive'] and q['role'] == 'WEREWOLF']
                    if wolves:
                        dragged_pid, dragged = random.choice(wolves)
                        dragged['alive'] = False
                        night_report['dragged'] = dragged['name']
                        room['log'].append(f"第{room['day']}夜: 猫又の道連れで {dragged['name']} も倒れました")
                break
    elif wt and wt == dt:
        night_report['guarded'] = True
        room['log'].append(f"第{room['day']}夜: 騎士が {wt} を護衛！")

    winner = check_win(room)
    if winner:
        room['phase'] = 'game_over'
        await bcast(room, {'type': 'game_over', 'winner': winner, 'eliminated': elim,
            'night_report': night_report,
            'players': [public_player(room, pid, p, include_role=True)
                        for pid, p in room['players'].items()], 'log': room['log']})
    else:
        await start_discussion(room, elim, night_report)

# ── 議論フェーズ ──────────────────────────────────────────────
async def start_discussion(room, elim=None, night_report=None):
    room['phase'] = 'discuss'
    room['disc_msgs'] = []
    room['disc_round'] = 1
    room['vote_ready'] = set()
    alive_pids = [pid for pid, p in room['players'].items() if p['alive']]
    alive_human_pids = [pid for pid in alive_pids if pid not in room['cpu_pids']]
    random.shuffle(alive_pids)
    room['disc_order'] = alive_pids
    room['disc_step'] = 0
    await bcast(room, {
        'type': 'discuss_start', 'day': room['day'], 'eliminated': elim,
        'night_report': night_report,
        'alive': [public_player(room, pid, p) for pid, p in room['players'].items() if p['alive']],
        'round': 1, 'total_rounds': DISC_ROUNDS,
        'readyTotal': len(alive_human_pids),
    })
    await _next_disc(room)

async def _check_vote_ready(room):
    if room['phase'] != 'discuss': return
    alive_human_pids = {pid for pid, p in room['players'].items() if p['alive'] and pid not in room['cpu_pids']}
    if alive_human_pids and room['vote_ready'].issuperset(alive_human_pids):
        await bcast(room, {'type': 'vote_ready_all', 'readyTotal': len(alive_human_pids)})
        await asyncio.sleep(1.7)
        if room['phase'] == 'discuss':
            await start_vote(room)

async def _next_disc(room):
    if room['phase'] != 'discuss': return
    while True:
        order = room['disc_order']
        step = room['disc_step']
        if step >= len(order):
            if room['disc_round'] < DISC_ROUNDS:
                room['disc_round'] += 1
                alive_pids = [pid for pid, p in room['players'].items() if p['alive']]
                random.shuffle(alive_pids)
                room['disc_order'] = alive_pids
                room['disc_step'] = 0
                await bcast(room, {'type': 'disc_new_round', 'round': room['disc_round']})
                continue
            await start_vote(room)
            return
        cur_pid = order[step]
        cur = room['players'].get(cur_pid)
        if cur and cur.get('alive'):
            break
        room['disc_step'] += 1
    cur_name = cur['name']
    await bcast(room, {'type': 'disc_turn', 'name': cur_name})
    if cur_pid in room['cpu_pids']:
        asyncio.create_task(_cpu_discuss(room, cur_pid))
    else:
        await send1(room, cur_pid, {'type': 'your_disc_turn'})

async def _cpu_discuss(room, cpu_pid):
    await asyncio.sleep(random.uniform(0.9, 2.4))
    if room['phase'] != 'discuss': return
    msg = cpu_template(room, cpu_pid)
    await _post_disc_msg(room, cpu_pid, msg)

async def _post_disc_msg(room, pid, text, advance_turn=True):
    p = room['players'][pid]
    room['disc_msgs'].append({'name': p['name'], 'text': text})
    await bcast(room, {'type': 'disc_message', 'name': p['name'], 'text': text})
    if not advance_turn:
        return
    room['disc_step'] += 1
    await asyncio.sleep(read_pause(text))
    await _next_disc(room)

# ── 投票 ────────────────────────────────────────────────────
async def start_vote(room):
    room['phase'] = 'vote'
    room['votes'] = {}
    room['vote_reasons'] = {}
    room['vote_pending'] = {pid for pid, p in room['players'].items() if p['alive']}
    await bcast(room, {'type': 'vote_start',
                       'alive': [public_player(room, pid, p) for pid, p in room['players'].items() if p['alive']]})
    for pid in list(room['vote_pending']):
        if pid in room['cpu_pids']:
            asyncio.create_task(_cpu_vote(room, pid))

async def _cpu_vote(room, cpu_pid):
    await asyncio.sleep(random.uniform(0.5, 2.0))
    if room['phase'] != 'vote': return
    p = room['players'][cpu_pid]
    wolf_set = {pid for pid, q in room['players'].items() if q['role'] == 'WEREWOLF'}
    alive_others = [(pid, q) for pid, q in room['players'].items() if q['alive'] and pid != cpu_pid]
    accused = {}
    for m in room['disc_msgs']:
        for _, q in alive_others:
            if q['name'] in m['text'] and any(w in m['text'] for w in ['怪しい','疑','投票','処刑']):
                accused[q['name']] = accused.get(q['name'], 0) + 1
    if p['role'] in ['WEREWOLF', 'MADMAN']:
        candidates = [q for pid, q in alive_others if pid not in wolf_set]
        target = (max(accused, key=accused.get) if accused else None) or (random.choice(candidates)['name'] if candidates else None)
    else:
        target = (max(accused, key=accused.get) if accused else None) or (random.choice(alive_others)[1]['name'] if alive_others else None)
    if target:
        room['votes'][p['name']] = target
        room['vote_reasons'][p['name']] = f"{target}さんの発言と投票の流れが気になりました。"
        room['vote_pending'].discard(cpu_pid)
        await bcast(room, {'type': 'vote_progress', 'done': len(room['votes']),
                           'total': len(room['votes']) + len(room['vote_pending'])})
        if not room['vote_pending']:
            await _tally_votes(room)

async def _tally_votes(room):
    tally = {}
    for tn in room['votes'].values(): tally[tn] = tally.get(tn, 0) + 1
    if tally:
        mv = max(tally.values())
        executed = random.choice([n for n, c in tally.items() if c == mv])
    else:
        candidates = [p['name'] for p in room['players'].values() if p.get('alive')]
        if not candidates:
            return
        executed = random.choice(candidates)
        tally = {executed: 0}
    erole = None
    nekomata_victim = None
    for pid, p in room['players'].items():
        if p['name'] == executed:
            p['alive'] = False; erole = p['role']
            room['last_executed'] = executed
            room['last_executed_role'] = erole
            room['log'].append(f"第{room['day']}日: {executed} が処刑されました")
            break
    if erole == 'NEKOMATA':
        bystanders = [(pid, p) for pid, p in room['players'].items() if p['alive']]
        if bystanders:
            victim_pid, victim = random.choice(bystanders)
            victim['alive'] = False
            nekomata_victim = victim['name']
            room['log'].append(f"第{room['day']}日: 猫又の道連れで {nekomata_victim} も倒れました")
    winner = check_win(room)
    msg = {'type': 'vote_result', 'executed': executed, 'executed_role': erole,
           'tally': tally, 'winner': winner, 'nekomata_victim': nekomata_victim,
           'vote_reasons': room.get('vote_reasons', {}),
           'votes': dict(room.get('votes', {}))}
    if winner:
        msg['players'] = [public_player(room, pid, p, include_role=True)
                          for pid, p in room['players'].items()]
        msg['log'] = room['log']
    await bcast(room, msg)

# ── メッセージハンドラ ─────────────────────────────────────────
async def handle(ws, pid, room, data):
    t = data.get('type')

    if t == 'set_cpu_count':
        if pid == room['host']:
            humans = len([ppid for ppid in room['players'] if ppid not in room['cpu_pids']])
            try:
                requested_cpu = int(data.get('count', 0))
            except (TypeError, ValueError):
                requested_cpu = 0
            room['desired_cpu'] = max(0, min(MAX_PLAYERS - humans, requested_cpu))
            await bcast(room, {'type': 'cpu_count_updated', 'count': room['desired_cpu']})

    elif t == 'start_game':
        if pid != room['host']: return
        n_human = len(room['players'])
        n_cpu = room['desired_cpu']
        n_total = n_human + n_cpu
        if n_total < 4:
            await send1(room, pid, {'type': 'error', 'msg': f'あと{4 - n_total}人必要です'}); return
        if n_total > MAX_PLAYERS:
            await send1(room, pid, {'type': 'error', 'msg': f'最大{MAX_PLAYERS}人までです'}); return
        existing_names = {p['name'] for p in room['players'].values()}
        cpu_pool = [n for n in CPU_NAMES if n not in existing_names]
        while len(cpu_pool) < n_cpu:
            cpu_pool.append(f'CPU{len(cpu_pool)+1}')
        names = random.sample(cpu_pool, n_cpu)
        for i in range(n_cpu):
            cpid = f'cpu{i}'
            room['players'][cpid] = {'name': names[i], 'ws': None, 'role': None, 'alive': True}
            room['cpu_pids'].add(cpid)
        cfg = list(CONFIGS.get(n_total, CONFIGS[6]))
        random.shuffle(cfg)
        for i, (ppid, p) in enumerate(room['players'].items()):
            p['role'] = cfg[i]; p['alive'] = True
        assign_avatar_indexes(room)
        room['phase'] = 'role_reveal'; room['day'] = 1
        room['last_doctor_target'] = None
        room['last_executed'] = None
        room['last_executed_role'] = None
        room['night_actions'] = {}
        room['night_pending'] = set()
        room['votes'] = {}
        room['vote_reasons'] = {}
        room['vote_pending'] = set()
        for ppid, p in room['players'].items():
            if ppid in room['cpu_pids']: continue
            wp = [q['name'] for qid, q in room['players'].items() if q['role'] == 'WEREWOLF' and qid != ppid] if p['role'] == 'WEREWOLF' else []
            sp = [q['name'] for qid, q in room['players'].items() if q['role'] == 'SHARED' and qid != ppid] if p['role'] == 'SHARED' else []
            await send1(room, ppid, {
                'type': 'game_started', 'role': p['role'], 'wolf_partners': wp, 'shared_partners': sp,
                'players': [public_player(room, qid, q) for qid, q in room['players'].items()],
                'is_host': ppid == room['host'],
            })

    elif t == 'start_night':
        if pid != room['host']: return
        if len(wolf_list(room)) >= 2: await start_wolf_chat(room)
        else: await start_night_actions(room)

    elif t == 'wolf_chat_msg':
        if room['phase'] != 'wolf_chat': return
        p = room['players'].get(pid)
        if not p or p['role'] != 'WEREWOLF': return
        text = str(data.get('text', ''))[:100]
        room['wolf_chat'].append({'name': p['name'], 'text': text})
        for wid in wolf_list(room):
            await send1(room, wid, {'type': 'wolf_chat_msg', 'name': p['name'], 'text': text})

    elif t == 'wolf_chat_done':
        room['wolf_done'].add(pid)
        human_wolves = [w for w in wolf_list(room) if w not in room['cpu_pids']]
        if room['wolf_done'].issuperset(set(human_wolves)):
            await start_night_actions(room)

    elif t == 'night_action':
        if room['phase'] != 'night': return
        await _apply_night_action(room, pid, data.get('action'), data.get('target'))

    elif t == 'disc_message':
        if room['phase'] != 'discuss': return
        p = room['players'].get(pid)
        if not p or not p.get('alive'): return
        text = str(data.get('text', '')).strip()[:220]
        if not text: return
        order = room['disc_order']
        is_turn = room['disc_step'] < len(order) and order[room['disc_step']] == pid
        await _post_disc_msg(room, pid, text, advance_turn=is_turn)

    elif t == 'vote_ready':
        if room['phase'] != 'discuss': return
        p = room['players'].get(pid)
        if not p or not p.get('alive'): return
        room['vote_ready'].add(pid)
        alive_human_pids = {rid for rid, rp in room['players'].items() if rp['alive'] and rid not in room['cpu_pids']}
        ready_names = [room['players'][rid]['name'] for rid in room['vote_ready'] if rid in alive_human_pids]
        await bcast(room, {'type': 'vote_ready_upd', 'readyNames': ready_names, 'readyTotal': len(alive_human_pids)})
        await _check_vote_ready(room)

    elif t == 'music_ended':
        if room['phase'] == 'discuss':
            await start_vote(room)

    elif t == 'vote':
        p = room['players'].get(pid)
        target = data.get('target')
        valid_targets = {q['name'] for q in room['players'].values() if q.get('alive')}
        if p and p.get('name') in valid_targets:
            valid_targets.discard(p['name'])
        if room['phase'] != 'vote' or not p or not p['alive'] or pid not in room['vote_pending'] or target not in valid_targets: return
        data['target'] = target
        room['votes'][p['name']] = data.get('target')
        room['vote_reasons'][p['name']] = str(data.get('reason') or f"{data.get('target')}さんの発言と投票の流れが気になりました。")[:160]
        room['vote_pending'].discard(pid)
        await send1(room, pid, {'type': 'vote_ack'})
        await bcast(room, {'type': 'vote_progress', 'done': len(room['votes']),
                           'total': len(room['votes']) + len(room['vote_pending'])})
        if not room['vote_pending']:
            await _tally_votes(room)

    elif t == 'next_night':
        if pid != room['host']: return
        room['day'] += 1
        if len(wolf_list(room)) >= 2: await start_wolf_chat(room)
        else: await start_night_actions(room)

# ── WebSocket エントリ ────────────────────────────────────────
async def ws_handler(ws):
    pid = None; room = None
    try:
        async for raw in ws:
            data = json.loads(raw)
            t = data.get('type')
            if t == 'create_room':
                code = gen_code(); room = new_room(code); rooms[code] = room
                pid = 'h'
                room['players'][pid] = {'name': data.get('name', 'ホスト'), 'ws': ws, 'role': None, 'alive': True}
                room['host'] = pid
                await ws.send(json.dumps({'type': 'room_created', 'code': code, 'pid': pid,
                                          'is_host': True, 'players': plist(room)}))
            elif t == 'join_room':
                code = normalize_code(data.get('code', ''))
                if code not in rooms:
                    await ws.send(json.dumps({'type': 'error', 'msg': '部屋が見つかりません'})); continue
                room = rooms[code]
                if room['phase'] != 'lobby':
                    await ws.send(json.dumps({'type': 'error', 'msg': 'ゲームはすでに始まっています'})); continue
                pid = f'p{len(room["players"])+1}'
                while pid in room['players']: pid += 'x'
                room['players'][pid] = {'name': data.get('name', 'プレイヤー'), 'ws': ws, 'role': None, 'alive': True}
                await ws.send(json.dumps({'type': 'room_joined', 'code': code, 'pid': pid,
                                          'is_host': False, 'players': plist(room)}))
                await bcast(room, {'type': 'player_joined', 'players': plist(room),
                                   'name': data.get('name')}, skip=pid)
            elif pid and room:
                await handle(ws, pid, room, data)
    except: pass
    finally:
        if pid and room:
            name = room['players'].get(pid, {}).get('name', '?')
            was_alive = room['players'].get(pid, {}).get('alive', False)
            was_voting = room.get('phase') == 'vote'
            was_discussing = room.get('phase') == 'discuss'
            was_current_disc = False
            if was_discussing:
                step = room.get('disc_step', 0)
                order = room.get('disc_order', [])
                was_current_disc = step < len(order) and order[step] == pid
            room['players'].pop(pid, None)
            if was_alive and was_voting:
                room['vote_pending'].discard(pid)
            if room['players']:
                if pid == room.get('host'):
                    nh = next((p for p in room['players'] if p not in room['cpu_pids']), None)
                    if nh:
                        room['host'] = nh
                        await send1(room, nh, {'type': 'became_host'})
                await bcast(room, {'type': 'player_left', 'players': plist(room), 'name': name})
                if was_alive and was_discussing and room.get('phase') == 'discuss':
                    if was_current_disc:
                        room['disc_step'] += 1
                        await _next_disc(room)
                    else:
                        await _check_vote_ready(room)
                if was_alive and was_voting:
                    await bcast(room, {'type': 'vote_progress', 'done': len(room.get('votes', {})),
                                       'total': len(room.get('votes', {})) + len(room.get('vote_pending', set()))})
                    if not room.get('vote_pending'):
                        await _tally_votes(room)
            else:
                rooms.pop(room['code'], None)

async def main():
    if websockets is None:
        print("pip install websockets")
        return
    try: ip = socket.gethostbyname(socket.gethostname())
    except: ip = 'localhost'
    print("=" * 45)
    print("🐺  人狼ゲーム オンラインサーバー")
    print("=" * 45)
    print(f"  ローカルIP : {ip}"); print(f"  ポート     : 8765")
    print(f"  接続先     : ws://{ip}:8765")
    print("=" * 45)
    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
