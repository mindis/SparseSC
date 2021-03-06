""" Utility functions
"""
import numpy as np
import itertools
from warnings import warn

from .warnings import SparseSCWarning

def simulation_eval(effects, CI_lowers, CI_uppers, true_effect=0):
    te_mse = np.mean(np.square((effects - true_effect)))
    cov = np.mean(
        np.logical_and(effects >= CI_lowers, effects <= CI_uppers).astype(int)
    )
    ci_len = np.mean(CI_uppers - CI_lowers)
    return (te_mse, cov, ci_len)


class CI_int(object):
    """
    Class to hold informatino for a confidence interval (for single point or for a vector)
    """

    def __init__(self, ci_low, ci_high, level):
        """
        :param ci_low: Low-bound
        :type ci_low: scalar or vector
        :param ci_high: High-bound
        :type ci_high: scalar or vector
        :param level: Level (1-alpha) for the CI interval
        :type level: float
        """
        self.ci_low = ci_low
        self.ci_high = ci_high
        self.level = level

    def __str__(self, i=None):
        if i is None:
            return "[%s ci: %s, %s]" % (self.level, self.ci_low, self.ci_high)
        return "[%s ci: %s, %s]" % (self.level, self.ci_low[i], self.ci_high[i])

    def __contains__(self, x):
        """
        test if a value is inside the confidence interval
        """
        if self.ci_low.size > 1:
            return RuntimeError(
                "`in` is not defined for more than one Confidence Interval"
            )
        return self.ci_low < x < self.ci_high


class EstResultCI(object):
    def __init__(self, effect, p, ci=None, placebos=None):
        """
        :param effect: Effect
        :type effect: Scalar or vector
        :param p: p-value 
        :type p: Scalar or vector
        :param ci: Confidence interval
        :type ci: CI_int
        :param placebos: Full matrix of placebos
        :type placebos: matrix
        """
        self.effect = effect
        self.p = p
        self.ci = ci
        self.placebos = placebos

    def __str__(self):
        def __ind_effect_str(effect, p):
            return str(effect) + " (p-value: " + str(p) + ")"

        try:
            iter(self.effect)
        except TypeError:
            ret_str = __ind_effect_str(self.effect, self.p)
            if self.ci is not None:
                ret_str = ret_str + " " + str(self.ci)
            return ret_str
        else:
            ret_str = ""
            for i in range(len(self.effect)):
                ret_str = ret_str + __ind_effect_str(self.effect[i], self.p[i])
                if self.ci is not None:
                    ret_str = ret_str + " " + str(self.ci)
                ret_str = ret_str + "\n"
            return ret_str

    def __contains__(self, x):
        """
        test if a value is inside the confidence interval
        """
        if not self.ci:
            raise RuntimeError("EstResultCI does not contain a confidence interval")
        return x in self.ci


class PlaceboResults(object):
    """
    Holds statistics for a vector of effects, include the full vector and
    two choices of aggregates (average and RMS)
    """
    def __init__(self, effect_vec, avg_joint_effect, rms_joint_effect, N_placebo):
        """
        :param effect_vec: Statistics for a vector of time-specific effects.
        :type effect_vec: EstResultCI
        :param avg_joint_effect: Statistics for the average effect.
        :type avg_joint_effect: EstResultCI
        :param rms_joint_effect: Statistics for the RMS effect
        :type rms_joint_effect: EstResultCI
        :param N_placebo: Number of placebos used for the statistis
        :type N_placebo: EstResultCI
        """
        self.effect_vec = effect_vec
        self.avg_joint_effect = avg_joint_effect
        self.rms_joint_effect = rms_joint_effect
        self.N_placebo = N_placebo


def _gen_placebo_stats_from_diffs(
    control_effect_vecs,
    effect_vecs,
    max_n_pl=1000000,
    ret_pl=False,
    ret_CI=False,
    level=0.95,
):
    """Generates placebo distribution to compare effects against. 
    For a single treated unit, this is just the control effects.
    If there are multiple treated units then the averaging process needs to be
    done to generate placebos also.
    Generates 2-sided p-values

    :param effect_vecs:
    :param control_effect_vecs:
    :param max_n_pl:
    :param ret_pl:
    :param ret_CI:
    :param level:

    Returns: 
        PlaceboResults: The Placebo test results
    """
    N1 = effect_vecs.shape[0]
    N0 = control_effect_vecs.shape[0]
    T1 = effect_vecs.shape[1]

    keep_pl = ret_pl or ret_CI

    # Get rest of the outcomes (already have effect_vecs)
    ##Get the RMSE joint effects
    rms_joint_effects = np.sqrt(np.mean(np.square(effect_vecs), axis=1))
    control_rms_joint_effects = np.sqrt(np.mean(np.square(control_effect_vecs), axis=1))
    ##Get the avg joint effects
    avg_joint_effects = np.mean(effect_vecs, axis=1)
    control_avg_joint_effects = np.mean(control_effect_vecs, axis=1)

    # Compute the outcomes for treatment
    effect_vec = np.mean(effect_vecs, axis=0)
    rms_joint_effect = np.mean(rms_joint_effects)
    avg_joint_effect = np.mean(avg_joint_effects)

    def _ncr(n, r):
        # https://stackoverflow.com/questions/4941753/is-there-a-math-ncr-function-in-python
        import operator as op
        import functools

        r = min(r, n - r)
        numer = functools.reduce(op.mul, range(n, n - r, -1), 1)  # from py2 xrange()
        denom = functools.reduce(op.mul, range(1, r + 1), 1)  # from py2 xrange()
        return numer // denom

    n_pl = _ncr(N0, N1)
    if max_n_pl > 0 & n_pl > max_n_pl:  # randomize
        comb_iter = itertools.combinations(range(N0), N1)
        comb_len = max_n_pl
    else:
        comb_iter = _random_combinations(n_pl, N0, N1)
        comb_len = n_pl

    if keep_pl:
        placebo_effect_vecs = np.empty((comb_len, T1))
        placebo_avg_joint_effects = np.empty(comb_len)
        placebo_rms_joint_effects = np.empty(comb_len)
    else:
        placebo_effect_vecs = None
        placebo_avg_joint_effects = None
        placebo_rms_joint_effects = None
    vec_p = np.zeros(T1)
    rms_joint_p = 0
    avg_joint_p = 0

    for idx, comb in enumerate(comb_iter):
        placebo_effect_vec = np.mean(control_effect_vecs[comb, :], 0)
        placebo_rms_joint_effect = np.mean(control_rms_joint_effects.take(comb))
        placebo_avg_joint_effect = np.mean(control_avg_joint_effects.take(comb))

        # p1s += (effect_vec_sgn*placebo_effect_vec >= effect_vec_sgn*effect_vec)
        # p1s_std += (effect_vec_sgn*placebo_std_effect_vec >= effect_vec_sgn*std_effect_vec)
        vec_p += abs(placebo_effect_vec) >= abs(effect_vec)
        rms_joint_p += placebo_rms_joint_effect >= rms_joint_effect
        avg_joint_p += abs(placebo_avg_joint_effect) >= abs(avg_joint_effect)
        if keep_pl:
            placebo_effect_vecs[idx, :] = placebo_effect_vec
            placebo_avg_joint_effects[idx] = placebo_avg_joint_effect
            placebo_rms_joint_effects[idx] = placebo_rms_joint_effect

    vec_p = _calculate_p_value(vec_p, comb_len)
    rms_joint_p = _calculate_p_value(rms_joint_p, comb_len)
    avg_joint_p = _calculate_p_value(avg_joint_p, comb_len)

    if ret_CI:
        # CI - All hypothetical true effects (beta0) that would not be reject
        # at the certain level To test non-zero beta0, apply beta0 to get
        # unexpected deviation beta_hat-beta0 and compare to permutation
        # distribution This means that we take the level-bounds of the
        # permutation distribution then "flip it around beta_hat" To make the
        # math a bit nicer, I will reject a hypothesis if pval<=(1-level)
        assert 0 < level < 1 and level > 0, "Use a level in [0,1]"
        alpha = 1 - level
        p2min = 2 / n_pl
        alpha_ind = max((1, round(alpha / p2min)))
        alpha = alpha_ind * p2min

        def _gen_CI(placebo_effects, alpha_ind, effect, null_is_zero=True):
            npl = placebo_effects.shape[0]
            sorted_eff = np.sort(placebo_effects)
            low_avg_effect = sorted_eff[alpha_ind]
            high_avg_effect = sorted_eff[(npl + 1) - alpha_ind]
            if (
                null_is_zero
                and np.sign(low_avg_effect) == np.sign(high_avg_effect)
                and low_avg_effect != 0
                and high_avg_effect != 0
            ):
                warn(
                    "CI doesn't contain 0. You might not have enough placebo effects.",
                    SparseSCWarning
                )
            return (effect - high_avg_effect, effect - low_avg_effect)

        CI_vec = np.empty((2, T1))
        for t in range(T1):
            CI_vec[:, t] = _gen_CI(placebo_effect_vecs[:, t], alpha_ind, effect_vec[t])
        CI_vec = CI_int(CI_vec[0, :], CI_vec[1, :], level)

        CI_avg = _gen_CI(placebo_avg_joint_effects, alpha_ind, avg_joint_effect)
        CI_avg = CI_int(CI_avg[0], CI_avg[1], level)
        CI_rms = _gen_CI(
            placebo_rms_joint_effects, alpha_ind, rms_joint_effect, null_is_zero=False
        )
        CI_rms = CI_int(CI_rms[0], CI_rms[1], level)

    else:
        CI_vec = None
        CI_avg = None
        CI_rms = None

    ret_struct = PlaceboResults(
        EstResultCI(effect_vec, vec_p, CI_vec, placebo_effect_vecs),
        EstResultCI(avg_joint_effect, avg_joint_p, CI_avg, placebo_avg_joint_effects),
        EstResultCI(rms_joint_effect, rms_joint_p, CI_rms, placebo_rms_joint_effects),
        comb_len,
    )

    return ret_struct


def _random_combinations(num, n, c):
    """
    https://stackoverflow.com/a/55307388/1519199

    Yields:
       Sequence[int]: a tuple ``c`` ints from ``range(n)``
    """
    i = 0
    while i < num:
        i += 1
        yield np.random.choice(n, c, replace=False)


def _calculate_p_value(npl_at_least_as_large, npl, incl_actual_in_set=True):
    """ADH10 incl_actual_in_set=True, CGNP13, ADH15 do not
    It depends on whether you (do|do not) you think the actual test is one of 
    the possible randomizations.
    p2s = 2*p1s #Ficher 2-sided p-vals (less common)
    """
    addition = int(incl_actual_in_set)
    return (npl_at_least_as_large + addition) / (npl + addition)
