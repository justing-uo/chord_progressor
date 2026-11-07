#!/usr/bin/env python3
#asks for a key and Roman numerals, prints the four-part voicing.


import re

LETTERS = 'CDEFGAB'
LETTER_PC = [0, 2, 4, 5, 7, 9, 11]
SCALE = {'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10]}
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
RANGES = [(40, 60), (48, 67), (55, 74), (60, 79)]  
FIGURES = {'': (0, False), '5': (0, False), '53': (0, False), '6': (1, False), '63': (1, False), '64': (2, False),
           '7': (0, True), '65': (1, True), '43': (2, True), '42': (3, True), '2': (3, True)}
ACC = {'#': 1, '♯': 1, 'b': -1, '♭': -1, '': 0}
INF = float('inf')


def parse_key(text):
    m = re.fullmatch(r'\s*([A-Ga-g])([#b♯♭]?)\s*(major|minor|maj|min|m)?\s*', text)
    if not m:
        raise ValueError(f'Not a key: {text!r}')
    letter, acc, word = m.groups()
    if word:
        mode = 'minor' if word.startswith('min') or word == 'm' else 'major'
    else:
        mode = 'minor' if letter.islower() else 'major'
    i = LETTERS.index(letter.upper())
    return {'letter': i, 'pc': (LETTER_PC[i] + ACC[acc]) % 12, 'mode': mode,
            'name': letter.upper() + acc + ' ' + mode}


def root_of(key, acc, numeral, quality):
    deg = ROMAN.index(numeral.upper())
    pc = key['pc'] + SCALE[key['mode']][deg] + ACC[acc]
    if key['mode'] == 'minor' and deg == 6 and quality in ('dim', 'halfdim'):
        pc += 1 
    return deg, (key['letter'] + deg) % 7, pc % 12


def parse_chord(key, text):
    t = text.replace('°', 'o')
    for a, b in (('6/4', '64'), ('6/5', '65'), ('4/3', '43'), ('4/2', '42')):
        t = t.replace(a, b)
    m = re.fullmatch(r'([b#♭♯]?)(vii|vi|v|iv|iii|ii|i)(o|ø|\+)?(\d*)(?:/([b#♭♯]?)(vii|vi|v|iv|iii|ii|i))?', t, re.I)
    if not m or (m.group(4) not in FIGURES and m.group(4) != ''):
        raise ValueError(f'Not a chord: {text!r}')
    acc, num, sym, fig, tacc, target = m.groups()
    if sym == 'ø' and fig == '':
        fig = '7'
    inv, seventh = FIGURES[fig]
    quality = ('aug' if sym == '+' else 'major') if num.isupper() else \
              {'o': 'dim', 'ø': 'halfdim'}.get(sym, 'minor')

    local = key 
    if target:
        _, tl, tpc = root_of(key, tacc, target, 'major' if target.isupper() else 'minor')
        local = {'letter': tl, 'pc': tpc, 'mode': 'major' if target.isupper() else 'minor'}

    deg, rl, rpc = root_of(local, acc, num, quality)
    third = 4 if quality in ('major', 'aug') else 3
    fifth = {'aug': 8, 'dim': 6, 'halfdim': 6}.get(quality, 7)
    tones = [('R', rpc, rl), ('3', (rpc + third) % 12, (rl + 2) % 7), ('5', (rpc + fifth) % 12, (rl + 4) % 7)]
    if seventh:
        if sym == 'o':
            sev = 9
        elif sym == 'ø':
            sev = 10
        else:  
            sev = (local['pc'] + SCALE[local['mode']][(deg + 6) % 7] - rpc) % 12
        tones.append(('7', (rpc + sev) % 12, (rl + 6) % 7))
    return {'label': text, 'tones': tones, 'inv': inv, 'seventh': seventh, 'pcs': {p for _, p, _ in tones},
            'dim': fifth == 6 and not seventh,
            'dominant': (deg == 4 and quality == 'major') or (deg == 6 and quality in ('dim', 'halfdim')),
            'tonic': local['pc'] % 12, 'lt': (local['pc'] - 1) % 12}


def spell(midi, letter):
    octave = midi // 12 - 1
    natural = 12 * (octave + 1) + LETTER_PC[letter]
    if natural - midi > 6:
        octave, natural = octave - 1, natural - 12
    elif midi - natural > 6:
        octave, natural = octave + 1, natural + 12
    acc = {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: '##'}[midi - natural]
    return LETTERS[letter] + acc + str(octave), octave * 7 + letter


def voicings(chord):
    """Every legal SATB spacing of one chord, with a cost for doubling, spacing and range."""
    tone = {pc: (role, letter) for role, pc, letter in chord['tones']}
    bass_pc = chord['tones'][chord['inv']][1]
    notes = [[m for m in range(lo, hi + 1) if m % 12 in tone] for lo, hi in RANGES]
    out = []
    for b in notes[0]:
        if b % 12 != bass_pc:
            continue
        for t in notes[1]:
            for a in notes[2]:
                for s in notes[3]:
                    if not (b < t <= a <= s and a - t <= 12 and s - a <= 12 and t - b <= 24):
                        continue
                    m = [b, t, a, s]
                    roles = [tone[x % 12][0] for x in m]
                    cost = doubling_cost(chord, m, roles)
                    if cost == INF:
                        continue
                    if t - b > 19: cost += (t - b - 19) * 0.5
                    if s > 76: cost += s - 76
                    if s < 64: cost += (64 - s) * 0.5
                    if a > 72: cost += a - 72
                    if t > 64: cost += t - 64
                    if s == a or a == t: cost += 2
                    names = [spell(x, tone[x % 12][1]) for x in m]
                    out.append({'m': m, 'roles': roles, 'names': [n for n, _ in names],
                                'steps': [s for _, s in names], 'cost': cost})
    return out


def doubling_cost(chord, m, roles):
    count = {r: roles.count(r) for r in 'R357'}
    if not count['R'] or not count['3']:
        return INF
    if chord['dominant'] and sum(x % 12 == chord['lt'] for x in m) > 1:
        return INF 
    if chord['seventh']:
        if count['7'] != 1:
            return INF
        if not count['5']:  
            return 1 if chord['inv'] == 0 and count['R'] == 2 else INF
        return 0
    if not count['5']:
        return 4 if chord['inv'] == 0 and count['R'] == 3 else INF
    doubled = next(r for r in 'R35' if count[r] == 2)
    if chord['inv'] == 2:
        return 0 if doubled == '5' else 3  
    if chord['dim']:
        return 0 if doubled == '3' else 1.5
    if chord['inv'] == 0:
        return {'R': 0, '5': 1.5, '3': 3}[doubled]
    return 1 if doubled == '3' else 0.3


def move_cost(c1, v1, c2, v2):
    """Cost of moving from one voicing to the next. INF means a rule is broken."""
    P, N = v1['m'], v2['m']
    mv = [n - p for p, n in zip(P, N)]
    if N[0] > P[1] or N[1] < P[0] or N[1] > P[2] or N[2] < P[1] or N[2] > P[3] or N[3] < P[2]:
        return INF  
    cost = 0
    for i in range(4):
        size, steps = abs(mv[i]), abs(v2['steps'][i] - v1['steps'][i])
        if size > 12 or (steps == 1 and size == 3) or (steps == 4 and size == 8):
            return INF 
        if steps == 3 and size == 6:
            cost += 6  
    for i in range(4):
        for j in range(i + 1, 4):
            before, after = (P[j] - P[i]) % 12, (N[j] - N[i]) % 12
            if mv[i] and mv[j] and before == after and before in (0, 7):
                return INF  
    outer = (N[3] - N[0]) % 12
    if outer in (0, 7) and mv[0] and (mv[0] > 0) == (mv[3] > 0) and abs(mv[3]) > 2:
        cost += 10  
    if c1['dominant'] and c1['tonic'] in c2['pcs']:
        for i in range(4):
            if P[i] % 12 == c1['lt'] and mv[i] != 1:
                if i in (0, 3):
                    return INF  
                cost += 2 if mv[i] == -4 and c2['inv'] == 0 else 12
    if c1['seventh']:
        for i in range(4):
            if v1['roles'][i] == '7' and mv[i] not in (-1, -2):
                cost += 4 if mv[i] == 0 else 15  
    if c1['inv'] == 2 and not c1['seventh'] and N[0] % 12 == P[0] % 12:
        for i in range(1, 4):
            if v1['roles'][i] in ('R', '3') and mv[i] not in (-1, -2):
                cost += 6  
    cost += abs(mv[0]) * 0.1 + (abs(mv[1]) + abs(mv[2])) * 0.5 + abs(mv[3]) * 0.45
    cost += sum(2 for x in mv[1:3] if abs(x) > 5) + (1 if abs(mv[3]) > 2 else 0) + (2.5 if abs(mv[3]) > 5 else 0)
    if all(x > 0 for x in mv) or all(x < 0 for x in mv):
        cost += 2
    if mv[0] and (mv[0] > 0) == (mv[3] > 0):
        cost += 0.8
    if mv[3] == 0:
        cost += 1.8
    return cost


def solve(chords):
    """Cheapest path through all voicings (dynamic programming)."""
    layers = [voicings(c) for c in chords]
    for c, layer in zip(chords, layers):
        if not layer:
            raise ValueError(f'No legal voicing for {c["label"]}')
    best = [[(v['cost'], None) for v in layers[0]]]
    for k in range(1, len(chords)):
        row = []
        for v in layers[k]:
            options = [(best[-1][j][0] + move_cost(chords[k - 1], u, chords[k], v), j)
                       for j, u in enumerate(layers[k - 1]) if best[-1][j][0] < INF]
            c, j = min(options, default=(INF, None))
            row.append((c + v['cost'], j))
        if all(c == INF for c, _ in row):
            raise ValueError(f'No way to connect {chords[k - 1]["label"]} -> {chords[k]["label"]} without breaking a rule')
        best.append(row)
    j = min(range(len(best[-1])), key=lambda i: best[-1][i][0])
    path = []
    for k in range(len(chords) - 1, -1, -1):
        path.append(layers[k][j])
        j = best[k][j][1]
    return path[::-1]


def main():
    print(__doc__)
    key = parse_key(input('Key: '))
    chords = [parse_chord(key, s) for s in input('Chords: ').replace(',', ' ').split()]
    path = solve(chords)
    width = max(6, max(len(c['label']) for c in chords) + 2)
    print(f'\n{key["name"]}\n   ' + ''.join(c['label'].ljust(width) for c in chords))
    for name, i in (('S', 3), ('A', 2), ('T', 1), ('B', 0)):
        print(f'{name}  ' + ''.join(v['names'][i].ljust(width) for v in path))


if __name__ == '__main__':
    try:
        main()
    except ValueError as e:
        print(e)
