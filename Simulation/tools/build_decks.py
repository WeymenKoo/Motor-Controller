"""Builds the LTspice decks for the FOC Motor Controller Rev 1 bench-correlation suite.
Every connection is a drawn wire; FLAGs are used only for ground, and to *name* a wire
(so .meas statements and B-source expressions can refer to it).

Design values come from the Rev 1 KiCad netlist (Project Outputs/Netlist) and the
firmware (Firmware/CLAUDE.md, app_config.h, app_params.c defaults)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascgen import Sheet, ltrun

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the Simulation folder
GND = '0'


# ----------------------------------------------------------------- placement helpers
def vpart(sh, kind, x, y, name, val, top, bot, spiceline=None, flip=False):
    """Vertical two-terminal part, top pin at (x, y). Returns the bottom pin.
    flip=True puts a diode's cathode on top (anode at the bottom)."""
    if kind in ('res', 'ind'):
        sh.sym(kind, x - 16, y - 16, 'R0', name, val, [top, bot], spiceline=spiceline); return (x, y + 80)
    if kind == 'cap':
        sh.sym('cap', x - 16, y, 'R0', name, val, [top, bot], spiceline=spiceline); return (x, y + 64)
    if kind in ('voltage', 'bv'):
        sh.sym(kind, x, y - 16, 'R0', name, val, [top, bot], spiceline=spiceline); return (x, y + 80)
    if kind in ('current', 'bi'):
        sh.sym(kind, x, y, 'R0', name, val, [top, bot], spiceline=spiceline); return (x, y + 80)
    if kind in ('diode', 'zener', 'TVSdiode'):
        if flip:
            sh.sym(kind, x + 16, y + 64, 'R180', name, val, [bot, top]); return (x, y + 64)
        sh.sym(kind, x - 16, y, 'R0', name, val, [top, bot]); return (x, y + 64)
    raise ValueError(kind)


def hpart(sh, kind, x, y, name, val, left, right, spiceline=None):
    """Horizontal two-terminal part, left pin at (x, y). Returns the right pin."""
    if kind in ('res', 'ind'):
        sh.sym(kind, x + 96, y - 16, 'R90', name, val, [right, left], spiceline=spiceline); return (x + 80, y)
    if kind == 'cap':
        sh.sym('cap', x + 64, y - 16, 'R90', name, val, [right, left], spiceline=spiceline); return (x + 64, y)
    raise ValueError(kind)


def gnd(sh, x, y):
    sh.flag(x, y, GND)


def hs_drive(gate, src, inp):
    """DRV8323 high-side gate driver as a current source: IDRIVEP (Isrc) until V(GH,SH) reaches VGSH,
    IDRIVEN / ISTRONG (Isnk) when off.  + pin = gate, - pin = SHx, so a positive current discharges the gate."""
    return ('I=Isnk*(1-V(%s))*tanh(V(%s,%s)/0.2)-Isrc*V(%s)*tanh((Vgsh-V(%s,%s))/0.2)'
            % (inp, gate, src, inp, gate, src))


def ls_drive(gate, inp):
    """Low-side driver, referenced to PGND (= board GND, not the FET source, which sits on the shunt)."""
    return 'I=Isnk*(1-V(%s))*tanh(V(%s)/0.2)-Isrc*V(%s)*tanh((Vgsl-V(%s))/0.2)' % (inp, gate, inp, gate)


def probe(sh, x, y, src, out, n):
    """10x passive probe on the DHO804: ground-lead inductance + loss, tip capacitance, then 70 MHz.
    Input is the left end at (x, y) (wire it to the node), output node `out` at the right."""
    p1 = hpart(sh, 'ind', x, y, 'Lgnd%d' % n, '{Lgnd}', src, 'PL%d' % n)
    p2 = hpart(sh, 'res', p1[0] + 16, y, 'Rgnd%d' % n, '{Rgnd}', 'PL%d' % n, 'PT%d' % n)
    sh.wire(p1, (p1[0] + 16, y))
    tip = (p2[0] + 32, y)
    sh.wire(p2, tip)
    b = vpart(sh, 'cap', tip[0], tip[1], 'Ctip%d' % n, '{Ctip}', 'PT%d' % n, GND); gnd(sh, *b)
    p3 = hpart(sh, 'res', tip[0] + 32, y, 'Rbw%d' % n, '10k', 'PT%d' % n, out)
    sh.wire(tip, (tip[0] + 32, y))
    o = (p3[0] + 48, y)
    sh.wire(p3, o)
    b = vpart(sh, 'cap', o[0], o[1], 'Cbw%d' % n, '{1/(2*pi*BWscope*10k)}', out, GND); gnd(sh, *b)
    sh.flag(o[0], o[1], out)
    return o


# =================================================================== 01 hot-plug
def deck01():
    sh = Sheet(2400, 1400)
    # supply + leads
    b = vpart(sh, 'voltage', 0, 0, 'Vsup', 'PWL(0 0 {tplug} 0 {tplug+tedge} {Vbus})', 'SUP', GND); gnd(sh, *b)
    sh.flag(0, 0, 'SUP')
    r = hpart(sh, 'res', 96, 0, 'Rlead', '{Rlead}', 'SUP', 'L1')
    sh.wire((0, 0), (96, 0))
    l = hpart(sh, 'ind', 240, 0, 'Llead', '{Llead}', 'L1', 'VBUS')
    sh.wire(r, (240, 0))
    # board: XT60 -> +VPROT rail
    sh.wire(l, (448, 0), (560, 0), (688, 0), (816, 0), (944, 0), (1072, 0))
    sh.flag(448, 0, 'VBUS')
    b = vpart(sh, 'cap', 560, 64, 'Cbulk', '{3*Cbulk}', 'VBUS', GND, spiceline='Rser={ESRbulk/3} Lser={ESLbulk/3}')
    sh.wire((560, 0), (560, 64)); gnd(sh, *b)
    b = vpart(sh, 'cap', 688, 64, 'Ccer', '{Ncer*Ccer}', 'VBUS', GND, spiceline='Rser=2m Lser=0.3n')
    sh.wire((688, 0), (688, 64)); gnd(sh, *b)
    b = vpart(sh, 'TVSdiode', 816, 64, 'D1', 'SMCJ51CA', 'VBUS', GND, flip=True)
    sh.wire((816, 0), (816, 64)); gnd(sh, *b)
    b = vpart(sh, 'res', 944, 64, 'Ridle', '{Vbus/Iidle}', 'VBUS', GND)
    sh.wire((944, 0), (944, 64)); gnd(sh, *b)
    # VBAT_SENSE divider (what the MCU / firmware OV check sees)
    b = vpart(sh, 'res', 1072, 64, 'R73', '12.4k', 'VBUS', 'VBAT_SENSE')
    sh.wire((1072, 0), (1072, 64))
    sh.wire(b, (1072, 176), (1200, 176)); sh.flag(1136, 176, 'VBAT_SENSE')
    b2 = vpart(sh, 'res', 1072, 192, 'R36', '2k', 'VBAT_SENSE', GND); gnd(sh, *b2)
    sh.wire((1072, 176), (1072, 192))
    b3 = vpart(sh, 'cap', 1200, 176, 'C60', '100n', 'VBAT_SENSE', GND); gnd(sh, *b3)

    sh.text(-80, -96, 'PROBE: DHO804 CH1 here (VBUS at the board side of the XT60)', size=1)
    sh.rect(400, -112, 1360, 400)
    sh.text(416, 368, 'FOC controller Rev 1 board (+VPROT net): C34/C37/C39 + 12x4u7 (C4,C5,C40..C80) + D1', size=1)
    sh.text(-80, 192, 'KA3005P (30 V / 5 A).\nHot-plug = XT60 mated into a\nlive supply at t = tplug.\nThe supply output is stiff\non this time scale (its 5 A\nCC loop is ms-slow).', size=1)
    sh.text(96, 64, '2 x 1 m 18 AWG + XT60\ncontact resistance', size=1)

    sh.text(-80, -520, '01 HOT-PLUG - 30 V KA3005P plugged into the board (XT60), bus overshoot vs the SMCJ51CA and the 100 V FETs', size=3)
    sh.text(-80, -472,
            'Question: when the XT60 is mated into a supply already at 30 V, how high does +VPROT ring, does D1 conduct, and what does the firmware see?\n'
            'The leads (Llead) resonate with the board capacitance; the electrolytics\' ESR is the only damping.  Undamped, the peak would be 2 x Vbus = 60 V,\n'
            'which is above D1\'s minimum breakdown (56.7 V).  PASS: Vbus_pk < 51 V (D1 stand-off: it never conducts) and far below 80 V (80 % of the FETs\' 100 V).\n'
            'Bench: DHO804 CH1 on VBUS (TP or C34 +), 10x probe, spring ground tip on C34 -, 10 V/div, 20 us/div, single trigger rising at 33 V.  Plug the XT60\n'
            'into the live supply.  Compare Vbus_pk and the ring period with the .meas results.  Also try it with the supply\'s OUTPUT button: that ramp is slow, no overshoot.',
            size=1)
    sh.text(1440, -440,
            'HOW TO EDIT (all in the .param line below)\n'
            '  Vbus     supply set-point, V                 (30)\n'
            '  Llead    lead loop inductance, H             (~1 uH per metre of a loose pair;\n'
            '           twisted pair ~0.5 uH/m) - stepped 0.5 / 2 uH\n'
            '  Rlead    leads + XT60, ohm                   (BM235 cannot resolve this well;\n'
            '           measure V drop at a known current instead)\n'
            '  Cbulk    one electrolytic, F                 (BM235 capacitance range: measure the\n'
            '  ESRbulk  ESR of ONE electrolytic, ohm (stepped whole bus at the XT60, board unpowered,\n'
            '           0.03 low-ESR / 0.3 general-purpose)\n'
            '  ESLbulk  ESL of ONE electrolytic, H           and set Cbulk = (C_meas - Ncer*4.7u)/3:\n'
            '                                                the ceramics read full value unbiased)\n'
            '  Ncer, Ccer  count and EFFECTIVE value of the 4u7/100 V X7R at 30 V DC bias\n'
            '  Iidle    board idle current, A               (read it off the KA3005P display)\n'
            'Back-solve the lead inductance from the scope: Llead = 1/((2*pi*f_ring)^2 * C_meas)', size=1)
    sh.text(-80, 480,
            '.param Vbus=30 Rlead=60m Llead=1u tplug=10u tedge=50n\n'
            '.param Cbulk=100u ESRbulk=0.3 ESLbulk=15n Ncer=12 Ccer=2.4u Iidle=0.06\n'
            '.step param ESRbulk list 0.03 0.3\n'
            '.step param Llead list 0.5u 2u\n'
            '.model SMCJ51CA D(BV=56.7 IBV=1m Rs=1.4 Cjo=2n)   ; VBR min 56.7 V, Vc 82.4 V @ 18.2 A -> 1.4 ohm\n'
            '.tran 0 1.2m 0 50n\n'
            '.meas TRAN Vbus_pk MAX V(VBUS)\n'
            '.meas TRAN overshoot_pct PARAM (Vbus_pk-Vbus)/Vbus*100\n'
            '.meas TRAN Ilead_pk MAX -I(Llead)\n'
            '.meas TRAN Itvs_pk MAX -I(D1)\n'
            '.meas TRAN t_1st WHEN V(VBUS)=Vbus RISE=1\n'
            '.meas TRAN t_2nd WHEN V(VBUS)=Vbus RISE=2\n'
            '.meas TRAN f_ring PARAM 1/(t_2nd-t_1st)\n'
            '.meas TRAN f_LC PARAM 1/(2*pi*sqrt(Llead*(3*Cbulk+Ncer*Ccer)))\n'
            '.meas TRAN Vsense_pk MAX V(VBAT_SENSE)\n'
            '.meas TRAN Vbus_fw_pk PARAM Vsense_pk*(12.4k+2k)/2k\n'
            '.meas TRAN Vbus_end FIND V(VBUS) AT 1.19m', directive=True)
    sh.text(1440, 0,
            'Notes\n'
            '- The electrolytic ESR is a guess (generic 10 mm 100 uF/100 V radial: 0.2-0.5 ohm).\n'
            '  It sets the damping: re-run with your measured ring decay if it differs.\n'
            '- Ccer = 2.4 uF effective: a 1210 4u7/100 V X7R loses ~50 % at 30 V DC bias.\n'
            '- Vbus_fw_pk is the bus voltage the MCU computes from VBAT_SENSE (12.4k/2k, 100 nF):\n'
            '  the 170 us filter hides most of the spike from the firmware OV check.\n'
            '- t_1st/t_2nd: successive upward crossings of Vbus = one ring period.\n'
            '  If the ring is overdamped they are not found; f_LC is the undamped value.', size=1)
    return sh


# =================================================================== 02 one leg switching
def deck02():
    sh = Sheet(2800, 1800)
    X = 64                       # leg column (FET drain/source x)
    # bus: Vbus (stiff, = supply + electrolytics) -> bulk/trace path -> +VPROT rail
    b = vpart(sh, 'voltage', -640, 0, 'Vbus', '{Vbus}', 'BULK', GND); gnd(sh, *b)
    sh.flag(-640, 0, 'BULK')
    p = hpart(sh, 'ind', -560, 0, 'Lbulk', '{Lbulk}', 'BULK', 'VPROT', spiceline='Rser={ESRbulk/3}')
    sh.wire((-640, 0), (-560, 0))
    sh.wire(p, (-352, 0), (-224, 0), (X, 0), (192, 0))
    sh.flag(-416, 0, 'VPROT')
    b = vpart(sh, 'cap', -352, 256, 'Ccer', '{4*Ccer}', 'VPROT', GND, spiceline='Rser=2m Lser={Lcer}')
    sh.wire((-352, 0), (-352, 256)); gnd(sh, *b)
    # C38 100n: +VPROT to SOURCE_A (local leg bypass, closes the loop above the shunt)
    b = vpart(sh, 'cap', -224, 256, 'C38', '100n', 'VPROT', 'SOURCE_A', spiceline='Rser=5m Lser=0.3n')
    sh.wire((-224, 0), (-224, 256))
    sh.wire(b, (-224, 576), (X, 576))
    # high-side FET
    b = vpart(sh, 'ind', X, 32, 'Ldh', '{Lpar}', 'VPROT', 'DH')
    sh.wire((X, 0), (X, 32)); sh.wire(b, (X, 128))
    sh.sym('nmos', X - 48, 128, 'R0', 'Q3', 'ISC030', ['DH', 'GH', 'SW'])
    sh.wire((X, 224), (X, 288), (X, 352))
    sh.flag(X, 112, 'DH')
    # low-side FET
    sh.sym('nmos', X - 48, 352, 'R0', 'Q4', 'ISC030', ['SW', 'GL', 'SL'])
    sh.wire((X, 448), (X, 480))
    b = vpart(sh, 'ind', X, 480, 'Lsl', '{Lpar}', 'SL', 'SOURCE_A')
    sh.flag(X, 464, 'SL')
    sh.wire(b, (X, 576), (X, 608))
    sh.flag(X, 592, 'SOURCE_A')
    b = vpart(sh, 'res', X, 608, 'R22', '{Rsh}', 'SOURCE_A', 'SH1')
    b = vpart(sh, 'ind', X, b[1] + 16, 'Lsh', '{Lsh}', 'SH1', GND)
    sh.wire((X, 688), (X, 704)); gnd(sh, *b)
    # gate drivers (DRV8323, IDRIVE current sources), left of each FET
    gx = X - 144
    b = vpart(sh, 'bi', gx, 208, 'Bgh', hs_drive('GH', 'SW', 'INH'), 'GH', 'SW')
    sh.wire((gx, 208), (X - 48, 208)); sh.flag(gx + 48, 208, 'GH')
    sh.wire(b, (gx, 288), (X, 288))
    vpart(sh, 'res', gx - 64, 208, 'Rpdh', '150k', 'GH', 'SW')
    sh.wire((gx - 64, 208), (gx, 208)); sh.wire((gx - 64, 288), (gx, 288))
    b = vpart(sh, 'bi', gx, 432, 'Bgl', ls_drive('GL', 'INL'), 'GL', GND)
    sh.wire((gx, 432), (X - 48, 432)); sh.flag(gx + 48, 432, 'GL'); gnd(sh, *b)
    b = vpart(sh, 'res', gx - 64, 432, 'Rpdl', '150k', 'GL', GND); gnd(sh, *b)
    sh.wire((gx - 64, 432), (gx, 432))
    # RC snubbers: R23/C35 across Q3, C36/R24 across Q4
    S = 224
    b = vpart(sh, 'res', S, 32, 'R23', '3.9', 'VPROT', 'SNH')
    sh.wire((192, 0), (S, 0), (S, 32))
    b = vpart(sh, 'cap', S, b[1] + 16, 'C35', '2.2n', 'SNH', 'SW')
    sh.wire((S, 112), (S, 128))
    sh.wire(b, (S, 288))
    sh.wire((X, 288), (S, 288))
    b = vpart(sh, 'cap', S, 352, 'C36', '2.2n', 'SW', 'SNL')
    sh.wire((S, 288), (S, 352))
    b = vpart(sh, 'res', S, b[1] + 16, 'R24', '3.9', 'SNL', 'SOURCE_A')
    sh.wire((S, 416), (S, 432))
    sh.wire(b, (S, 576), (X, 576))
    # motor phase: a current source over one edge (L/R of the winding = 96 us >> edge time)
    sh.wire((S, 288), (416, 288), (560, 288))
    sh.flag(352, 288, 'SW')
    b = vpart(sh, 'current', 416, 288, 'Iph', '{Iph}', 'SW', GND); gnd(sh, *b)
    # scope probes
    probe(sh, 560, 288, 'SW', 'SW_SCOPE', 1)
    sh.flag(560, 528, 'GL')
    probe(sh, 560, 528, 'GL', 'GL_SCOPE', 2)
    # PWM inputs from the MCU (TIM1 CH1 / CH1N with 200 ns dead time)
    b = vpart(sh, 'voltage', -640, 512, 'Vinh', 'PULSE(0 1 {T/4+DT/2} 2n 2n {T/2-DT} {T})', 'INH', GND); gnd(sh, *b)
    sh.flag(-640, 512, 'INH')
    b = vpart(sh, 'voltage', -480, 512, 'Vinl', 'PULSE(1 0 {T/4-DT/2} 2n 2n {T/2+DT} {T})', 'INL', GND); gnd(sh, *b)
    sh.flag(-480, 512, 'INL')

    sh.text(-700, 640, 'MCU PWM (TP21 / TP22):\nINH = PWM_PHASEA_H, INL = PWM_PHASEA_L.\n1 = on.  DRV8323 6x mode.', size=1)
    sh.text(-60, 300, 'SHA', size=1)
    sh.text(-300, 760, 'Bgh/Bgl = DRV8323 gate drive: IDRIVEP source until VGS = VGSH/VGSL,\nIDRIVEN/ISTRONG sink when off. Rpd = 150k passive pull-downs (RPD).\nR20/R21 (0R) omitted.', size=1)
    sh.text(432, 384, 'motor phase A\n(ID_R hold)', size=1)
    sh.text(560, 336, 'CH1: SW, 10x probe', size=1)
    sh.text(560, 576, 'CH2: GL (GLA, TP39)', size=1)
    sh.text(256, 160, 'RC snubbers', size=1)

    sh.text(-700, -560, '02 ONE LEG SWITCHING - phase A at 30 V, +5 A and -2.5 A (the two currents of an ID_R hold), what the DHO804 should show', size=3)
    sh.text(-700, -512,
            'Question: switch-node edge rate, overshoot/undershoot, the body-diode step in the 200 ns dead time, and Miller-induced VGS on the off FET, at the real IDRIVE.\n'
            'Step 2 (Iph = +5 A, out of the leg = phase A in an ID_R hold): the HS turn-on is the hard edge (rising), HS turn-off is soft (the current pulls SW down).\n'
            'Step 1 (Iph = -2.5 A, into the leg = phase B or C in the same hold): roles swap, the LS turn-on is the hard edge (falling).\n'
            'PASS: Vds_pk < 80 V (80 % of 100 V), VgsL_miller < 2.3 V (VGS(th) min), and the shunt node back inside the CSA range (+-0.3 V) well before the sample.\n'
            'The firmware open item "switch node NOT verified, a DMM read 75 V" is answered here: Vsw_pk is the true peak. Do not use the BM235 on SW (it averages a 25 kHz square).',
            size=1)
    sh.text(1000, -440,
            'HOW TO EDIT (.param lines below)\n'
            '  Vbus        bus voltage, V                          (30)\n'
            '  Iph         phase current at the edge, A            (stepped -2.5 / +5)\n'
            '  Isrc, Isnk  DRV8323 IDRIVEP / IDRIVEN, A            (p_drv_idrive code 15 = 1.0 / 2.0 A)\n'
            '  Vgsh, Vgsl  gate drive voltage, V                    (VGSH/VGSL, 11 V at VM > 13 V)\n'
            '  DT          dead time, s                             (TIM1 DTG=34 -> 200 ns)\n'
            '  T           PWM period, s                            (1/25 kHz, APP_PWM_FREQ_HZ)\n'
            '  Lpar        layout inductance per FET lead, H       (estimate; raise it if the scope rings lower)\n'
            '  Lgnd, Rgnd  probe ground lead: ~150 nH for the 15 cm clip, ~10 nH for the spring tip\n'
            '  BWscope     DHO804 bandwidth (70 MHz)\n'
            'Motor: an edge only sees the current (the winding is 9.44 uH / 98 mOhm, L/R = 96 us).', size=1)
    sh.text(-700, 880,
            '.include ../lib/ISC030N10NM6_fit.lib\n'
            '.param Vbus=30 Iph=5 T={1/25k} DT=200n\n'
            '.param Isrc=1.0 Isnk=2.0 Vgsh=11 Vgsl=11\n'
            '.param Rsh=3m Lsh=0.6n Lpar=0.5n Lbulk=10n ESRbulk=0.3 Ccer=2.4u Lcer=0.3n\n'
            '.param Lgnd=150n Rgnd=20 Ctip=12p BWscope=70Meg\n'
            '.step param Iph list -2.5 5   ; LTspice runs list values in ascending order: step 1 = -2.5 A, step 2 = +5 A\n'
            '.nodeset V(GL)=11 V(GH)=0 V(SW)=0 V(VPROT)=30 V(DH)=30   ; DC starting guess only\n'
            '.tran 0 36u 0 1n\n'
            '.options plotwinsize=0\n'
            '.meas TRAN t_r10 WHEN V(SW)={0.1*Vbus} RISE=1 TD={T/8}\n'
            '.meas TRAN t_r90 WHEN V(SW)={0.9*Vbus} RISE=1 TD={T/8}\n'
            '.meas TRAN t_rise PARAM t_r90-t_r10\n'
            '.meas TRAN dvdt_rise_Vns PARAM 0.8*Vbus/t_rise/1e9\n'
            '.meas TRAN t_f90 WHEN V(SW)={0.9*Vbus} FALL=1 TD={T/2}\n'
            '.meas TRAN t_f10 WHEN V(SW)={0.1*Vbus} FALL=1 TD={T/2}\n'
            '.meas TRAN t_fall PARAM t_f10-t_f90\n'
            '.meas TRAN dvdt_fall_Vns PARAM 0.8*Vbus/t_fall/1e9', directive=True)
    sh.text(260, 880,
            '.meas TRAN Vsw_pk MAX V(SW) FROM 2u\n'
            '.meas TRAN Vsw_min MIN V(SW) FROM 2u\n'
            '.meas TRAN Vsw_pk_scope MAX V(SW_SCOPE) FROM 2u\n'
            '.meas TRAN Vsw_min_scope MIN V(SW_SCOPE) FROM 2u\n'
            '.meas TRAN Vds_hs_pk MAX V(DH,SW) FROM 2u\n'
            '.meas TRAN Vds_ls_pk MAX V(SW,SL) FROM 2u\n'
            '.meas TRAN Vsw_dead1 FIND V(SW) AT {T/4}\n'
            '.meas TRAN Vsw_dead2 FIND V(SW) AT {3*T/4}\n'
            '.meas TRAN VgsL_miller MAX V(GL,SL) FROM {T/4+DT/2} TO {T/4+DT/2+1u}\n'
            '.meas TRAN VgsH_miller MAX V(GH,SW) FROM {3*T/4+DT/2} TO {3*T/4+DT/2+1u}\n'
            '.meas TRAN VgsL_pk_scope MAX V(GL_SCOPE) FROM {T/4+DT/2} TO {T/4+DT/2+1u}\n'
            '.meas TRAN Vshunt_max MAX V(SOURCE_A) FROM 2u\n'
            '.meas TRAN Vshunt_min MIN V(SOURCE_A) FROM 2u\n'
            '.meas TRAN Vshunt_on FIND V(SOURCE_A) AT {T/8}\n'
            '.meas TRAN Vgh_on FIND V(GH,SW) AT {T/2}\n'
            '.meas TRAN Vgl_on FIND V(GL) AT {T/8}', directive=True)
    sh.text(1000, 0,
            'Notes\n'
            '- Layout parasitics (Lpar, Lsh, Lcer, Lbulk) are estimates for a 2-layer-equivalent\n'
            '  TDSON-8 half-bridge; they set the ring frequency and overshoot, so treat Vsw_pk as\n'
            '  model-dependent and correct Lpar from the measured ring frequency.\n'
            '- V(SW) is the true node; V(SW_SCOPE) is what a 10x probe with its ground clip on a\n'
            '  70 MHz scope shows. Use the spring ground tip: the 15 cm clip adds its own ~100 MHz ring.\n'
            '- High-side VGS cannot be probed directly with earth-referenced probes: CH3 on GH (TP37)\n'
            '  and use CH3 - CH1 math. That math is only meaningful away from the edges.\n'
            '- MOSFET: ISC030N10NM6 behavioural VDMOS fit (lib/), not the Infineon model.\n'
            '  Checked against the datasheet: Rds(on) 2.55 mOhm, plateau 4.6 V, Qg 55 nC, Qgd 9.6 nC.\n'
            '- Bench: needs a PWM build at 30 V. Every approved scope so far is 12 V and the firmware\n'
            '  refuses ID / spin above 15 V: raising that is a separate, reviewed change.', size=1)
    return sh


# =================================================================== 03 standstill current + CSA
def deck03():
    sh = Sheet(3200, 2200)
    legs = [('A', 64), ('B', 448), ('C', 832)]
    # supply + leads + bus capacitance
    b = vpart(sh, 'voltage', -960, 0, 'Vsup', '{Vbus}', 'SUP', GND); gnd(sh, *b)
    sh.flag(-960, 0, 'SUP')
    p = hpart(sh, 'res', -896, 0, 'Rlead', '60m', 'SUP', 'L1')
    sh.wire((-960, 0), (-896, 0))
    p = hpart(sh, 'ind', -800, 0, 'Llead', '1u', 'L1', 'VPROT')
    sh.wire((-816, 0), (-800, 0))
    sh.wire(p, (-576, 0), (-448, 0), (-224, 0))
    sh.flag(-640, 0, 'VPROT')
    b = vpart(sh, 'cap', -576, 64, 'Cbulk', '300u', 'VPROT', GND, spiceline='Rser=0.1'); gnd(sh, *b)
    sh.wire((-576, 0), (-576, 64))
    b = vpart(sh, 'cap', -448, 64, 'Ccer', '28u', 'VPROT', GND, spiceline='Rser=2m'); gnd(sh, *b)
    sh.wire((-448, 0), (-448, 64))
    sh.wire((-224, 0), (64, 0), (448, 0), (832, 0))
    phase_x = {}
    for ph, X in legs:
        q_hi, q_lo = {'A': ('Q3', 'Q4'), 'B': ('Q5', 'Q6'), 'C': ('Q7', 'Q8')}[ph]
        rs = {'A': 'R22', 'B': 'R27', 'C': 'R32'}[ph]
        sw, gh, gl, src = 'SW_' + ph, 'GH' + ph, 'GL' + ph, 'SRC_' + ph
        sh.wire((X, 0), (X, 128))
        sh.sym('nmos', X - 48, 128, 'R0', q_hi, 'ISC030', ['VPROT', gh, sw])
        sh.wire((X, 224), (X, 288), (X, 352))
        sh.sym('nmos', X - 48, 352, 'R0', q_lo, 'ISC030', [sw, gl, src])
        sh.wire((X, 448), (X, 528))
        sh.flag(X, 512, src)
        b = vpart(sh, 'res', X, 528, rs, '{Rsh}', src, GND); gnd(sh, *b)
        gx = X - 144
        b = vpart(sh, 'bi', gx, 208, 'Bgh' + ph, hs_drive(gh, sw, 'INH' + ph), gh, sw)
        sh.wire((gx, 208), (X - 48, 208)); sh.flag(gx + 48, 208, gh)
        sh.wire(b, (gx, 288), (X, 288))
        vpart(sh, 'res', gx - 64, 208, 'Rpdh' + ph, '150k', gh, sw)
        sh.wire((gx - 64, 208), (gx, 208)); sh.wire((gx - 64, 288), (gx, 288))
        b = vpart(sh, 'bi', gx, 432, 'Bgl' + ph, ls_drive(gl, 'INL' + ph), gl, GND)
        sh.wire((gx, 432), (X - 48, 432)); sh.flag(gx + 48, 432, gl); gnd(sh, *b)
        b = vpart(sh, 'res', gx - 64, 432, 'Rpdl' + ph, '150k', gl, GND); gnd(sh, *b)
        sh.wire((gx - 64, 432), (gx, 432))
        # phase wire down to the motor
        px = X + 96
        sh.wire((X, 288), (px, 288), (px, 768))
        sh.flag(px, 288, sw)
        phase_x[ph] = px
    # motor: R + L per phase into the star point
    for ph, X in legs:
        px = phase_x[ph]
        b = vpart(sh, 'res', px, 768, 'Rph' + ph, '{Rph}', 'SW_' + ph, 'M' + ph)
        b = vpart(sh, 'ind', px, b[1] + 16, 'L' + ph, '{Lph}', 'M' + ph, 'N')
        sh.wire((px, 848), (px, 864))
        sh.wire(b, (px, 976))
    sh.wire((phase_x['A'], 976), (phase_x['B'], 976), (phase_x['C'], 976))
    sh.flag(phase_x['B'] + 64, 976, 'N')
    sh.rect(phase_x['A'] - 112, 736, phase_x['C'] + 336, 1024)
    sh.text(phase_x['C'] + 112, 784, 'T-Motor MN601-S (KV320)\nfirmware ID 2026-09-27:\nR 98 mOhm, Ld 7.9 uH, Lq 11.0 uH\nstandstill -> no back-EMF', size=1)

    # current sense amplifiers A and B (DRV8323 CSA, gain G, VREF/2 bias) + MCU RC filter (56R / 2n2)
    for k, (ph, rs, rf, cf) in enumerate([('A', 'R22', 'R15', 'C27'), ('B', 'R27', 'R14', 'C26')]):
        x0, y0 = 1440, 160 + k * 352
        b = vpart(sh, 'bv', x0, y0, 'Bcsa' + ph, 'V=VREF/2-G*V(SRC_%s)' % ph, 'CI' + ph, GND); gnd(sh, *b)
        p = hpart(sh, 'res', x0, y0, 'Rset' + ph, '1k', 'CI' + ph, 'CO' + ph)
        b = vpart(sh, 'cap', p[0] + 32, y0, 'Cset' + ph, '{tSET/4.6/1k}', 'CO' + ph, GND); gnd(sh, *b)
        sh.wire(p, (p[0] + 32, y0)); sh.flag(p[0] + 32, y0, 'CO' + ph)
        ox = p[0] + 176
        b = vpart(sh, 'bv', ox, y0, 'Bso' + ph, 'V=limit(V(CO%s),0.25,VREF-0.25)' % ph, 'SO' + ph, GND); gnd(sh, *b)
        sh.flag(ox, y0, 'SO' + ph)
        p = hpart(sh, 'res', ox + 16, y0, rf, '56', 'SO' + ph, 'FILTER_SO' + ph)
        sh.wire((ox, y0), (ox + 16, y0))
        b = vpart(sh, 'cap', p[0] + 48, y0, cf, '2.2n', 'FILTER_SO' + ph, GND); gnd(sh, *b)
        sh.wire(p, (p[0] + 48, y0))
        sh.flag(p[0] + 48, y0, 'FILTER_SO' + ph)
        sh.text(x0 - 48, y0 - 72, 'CSA %s: SP%s = SRC_%s, SN%s = GND (Kelvin)   settling   SOx pin    -> MCU ADC (TP%d)' % (ph, ph, ph, ph, 17 if ph == 'A' else 16), size=1)
    sh.rect(1360, 64, 2160, 768)
    sh.text(1376, 720, 'DRV8323 CSA: SOx = VREF/2 - G x (SPx - SNx).  Positive phase current (out of the leg) flows UP\nthrough the low-side shunt, so SOx rises above VREF/2 (matches the firmware sign, APP_CSA_SIGN_A = +1).', size=1)

    # control: carrier, PI current regulator on alpha (as RUN ID_R), duties, dead-time PWM logic
    cx, cy = -1344, 448
    b = vpart(sh, 'voltage', cx, cy, 'Vtri', 'PULSE(0 1 0 {1/(2*fsw)} {1/(2*fsw)} 0 {1/fsw})', 'TRI', GND); gnd(sh, *b)
    sh.flag(cx, cy, 'TRI')
    b = vpart(sh, 'bv', cx + 224, cy, 'Bpi', 'V=Kp*(Iset-I(LA))+Ki*idt(Iset-I(LA),u0/Ki)', 'U', GND); gnd(sh, *b)
    sh.flag(cx + 224, cy, 'U')
    b = vpart(sh, 'bv', cx + 448, cy, 'BdA', 'V=0.5+2/3*V(U)', 'DA', GND); gnd(sh, *b)
    sh.flag(cx + 448, cy, 'DA')
    b = vpart(sh, 'bv', cx + 672, cy, 'BdBC', 'V=0.5-1/3*V(U)', 'DBC', GND); gnd(sh, *b)
    sh.flag(cx + 672, cy, 'DBC')
    for k, (ph, d) in enumerate([('A', 'DA'), ('B', 'DBC'), ('C', 'DBC')]):
        x = cx + k * 224
        y = cy + 256
        b = vpart(sh, 'bv', x, y, 'Bh' + ph, 'V=0.5+0.5*tanh(2000*(V(%s)-V(TRI)-DT*fsw))' % d, 'INH' + ph, GND); gnd(sh, *b)
        sh.flag(x, y, 'INH' + ph)
        b = vpart(sh, 'bv', x, y + 192, 'Bl' + ph, 'V=0.5+0.5*tanh(2000*(V(TRI)-V(%s)-DT*fsw))' % d, 'INL' + ph, GND); gnd(sh, *b)
        sh.flag(x, y + 192, 'INL' + ph)
    sh.rect(cx - 64, cy - 96, cx + 880, cy + 560)
    sh.text(cx - 48, cy - 80, 'MCU (TIM1 centre-aligned, 25 kHz, 200 ns dead time) + PI current loop on alpha, like RUN ID_R.\n'
                              'HS on while duty > carrier; LS on around the carrier peak, where the ADC samples.', size=1)

    sh.text(-1000, -600, '03 STANDSTILL CURRENT + CSA - 5 A along +alpha (phase A +5 A, B and C -2.5 A each), 30 V, 25 kHz centre-aligned', size=3)
    sh.text(-1000, -552,
            'Question: at the firmware\'s ID_R / hold operating point, what phase-current ripple does the MN601-S\'s low inductance give, what does the CSA output look like\n'
            'on the scope, and has it settled when the ADC samples at the carrier peak?  This is also the scale/offset check: I_from_CSA vs the true winding current.\n'
            'PASS: IA_avg within 2 % of Iset; CSA-derived current within 2 % of the true current at the sample instant; SOA flat at VREF/2 while the high side conducts.\n'
            'Bench (RUN ID_R or a HOLD at Iset, MN601-S clamped): DHO804 CH1 on SOA (TP20) or FILTER_SOA (TP17), CH2 on PWM_PHASEA_L (TP22) as the trigger, CH3 on SW_A.\n'
            'BM235 in series with the supply (10 A range) or the KA3005P display: compare with Isup_avg.  Firmware GUI current reading: compare with IA_csa.', size=1)
    sh.text(1440, -520,
            'HOW TO EDIT (.param lines below)\n'
            '  Vbus             bus voltage, V                       (30)\n'
            '  Iset             held current along +alpha, A         (5; phase A carries Iset, B and C -Iset/2)\n'
            '  R_meas           phase resistance from firmware ID_R  (98 mOhm; matches the DC line-line 195 mOhm,\n'
            '                   so it is motor + leads; the FETs and shunts are modelled separately)\n'
            '  Ld, Lq           firmware ID_L, H                     (7.9 / 11.0 uH; the sim uses the mean, as the firmware)\n'
            '  lambda, pp, J    flux linkage 1.389 mV.s, 14 pole pairs, 8e-5 kg.m2: not used at standstill,\n'
            '                   listed so all firmware motor constants live on one sheet\n'
            '  fsw, DT          25 kHz, 200 ns                       (APP_PWM_FREQ_HZ, TIM1 DTG=34)\n'
            '  G, VREF, tSET    CSA gain 20 (p_csa_gain), 3.3 V, 600 ns settling to 1 % at G=20 (datasheet)\n'
            '  fc               PI current-loop crossover in this model only (the firmware loop is digital)', size=1)
    sh.text(-1000, 1120,
            '.include ../lib/ISC030N10NM6_fit.lib\n'
            '.param Vbus=30 Iset=5 fsw=25k DT=200n\n'
            '.param R_meas=98m Ld=7.9u Lq=11.0u lambda=1.389m pp=14 J=8e-5\n'
            '.param Rph=R_meas Lph={(Ld+Lq)/2}\n'
            '.param Rsh=3m G=20 VREF=3.3 tSET=600n\n'
            '.param Isrc=1.0 Isnk=2.0 Vgsh=11 Vgsl=11\n'
            '.param fc=1k Kp={2*pi*fc*1.5*Lph/Vbus} Ki={Kp*Rph/Lph}\n'
            '.param u0={(1.5*(Rph+4m)*Iset+2*Vbus*DT*fsw)/Vbus}   ; feed-forward start (R drop + dead-time loss)\n'
            '.ic I(LA)={Iset} I(LB)={-Iset/2} I(LC)={-Iset/2}\n'
            '.param ts={24.5/fsw}   ; ADC sample instant = carrier peak (centre of the low-side window)\n'
            '.tran 0 1m 0 2n\n'
            '.options plotwinsize=0', directive=True)
    sh.text(-160, 1120,
            '.meas TRAN IA_avg AVG I(LA) FROM {21/fsw} TO {25/fsw}\n'
            '.meas TRAN IA_pp PP I(LA) FROM {23/fsw} TO {25/fsw}\n'
            '.meas TRAN IB_avg AVG I(LB) FROM {21/fsw} TO {25/fsw}\n'
            '.meas TRAN IA_true FIND I(LA) AT ts\n'
            '.meas TRAN SOA_s FIND V(FILTER_SOA) AT ts\n'
            '.meas TRAN IA_csa PARAM (SOA_s-VREF/2)/(G*Rsh)\n'
            '.meas TRAN IA_err_pct PARAM (IA_csa-IA_true)/IA_true*100\n'
            '.meas TRAN IB_true FIND I(LB) AT ts\n'
            '.meas TRAN SOB_s FIND V(FILTER_SOB) AT ts\n'
            '.meas TRAN IB_csa PARAM (SOB_s-VREF/2)/(G*Rsh)\n'
            '.meas TRAN IB_err_pct PARAM (IB_csa-IB_true)/IB_true*100\n'
            '.meas TRAN SOA_hs FIND V(SOA) AT {24/fsw}\n'
            '.meas TRAN SOA_pp PP V(SOA) FROM {24/fsw} TO {25/fsw}\n'
            '.meas TRAN duty_A FIND V(DA) AT ts\n'
            '.meas TRAN Isup_avg AVG -I(Vsup) FROM {15/fsw} TO {25/fsw}\n'
            '.meas TRAN Psup PARAM Isup_avg*Vbus\n'
            '.meas TRAN Pcopper PARAM 1.5*Rph*Iset**2', directive=True)
    sh.text(640, 1120,
            'Notes\n'
            '- Ripple: the hold needs only ~1 V line-line, so the active vectors are short;\n'
            '  ripple is roughly V_applied x T / L and barely depends on Vbus.  At speed (back-EMF)\n'
            '  the active vectors grow and so does the ripple: re-check before closed-loop FOC.\n'
            '- The firmware samples once per period at the carrier peak (centre of the low-side window),\n'
            '  where the ripple crosses its mean, so IA_csa reads the average current, not the peak.\n'
            '- FETs: no layout parasitics or snubbers here (deck 02 covers the edges).\n'
            '- CSA model: ideal gain + one pole set from tSET, output clipped to the linear range\n'
            '  (0.25 V .. VREF-0.25 V). Offset (+-4 mV = +-67 mA at G=20, 3 mOhm) is calibrated out by\n'
            '  the firmware CSA_CAL and is not modelled.\n'
            '- Bench: needs a PWM build at 30 V and Iset 5 A: above every approved scope (12 V, 3 A cap,\n'
            '  ID modes refused above 15 V). Simulation only until that scope is reviewed.', size=1)
    return sh


DECKS = {'01_hot_plug': deck01, '02_leg_switching': deck02, '03_standstill_csa': deck03}

if __name__ == '__main__':
    want = sys.argv[1:] or list(DECKS)
    for name in want:
        sh = DECKS[name]()
        d = os.path.join(OUT, name)
        os.makedirs(os.path.join(d, 'results'), exist_ok=True)
        asc = os.path.join(d, name + '.asc')
        sh.write(asc)
        ltrun(asc, netlist=True)
        net = asc[:-4] + '.net'
        errs = sh.check(net)
        sh.render(os.path.join(d, 'results', 'schematic_preview.png'), name)
        print(name, 'NETLIST OK' if not errs else '\n  '.join(['NETLIST ERRORS:'] + errs))
