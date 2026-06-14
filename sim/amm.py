"""
amm.py — Reference implementations of three AMM families used in the BitDA
final project: Constant-Product (Uniswap V2/V3), Stable-Swap (Curve) and
Weighted-Pool (Balancer).

All math follows the primary whitepapers:
  - Uniswap V2 / V3 whitepapers (Adams et al. 2020, 2021)
  - Curve StableSwap whitepaper (Egorov 2019)
  - Balancer whitepaper (Martinelli & Mushegian 2019)

Everything is implemented with floating-point and scipy root finders for
clarity (the on-chain contracts use fixed-point integer Newton iterations,
which give the same curve shape).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


# --------------------------------------------------------------------------
# Constant-Product (Uniswap V2):  x * y = k
# --------------------------------------------------------------------------
class ConstantProduct:
    """50/50 constant-product pool with a proportional fee (default 0.30%)."""

    def __init__(self, x: float, y: float, fee: float = 0.003):
        self.x = float(x)            # reserve of asset X (e.g. the volatile token)
        self.y = float(y)            # reserve of asset Y (e.g. the numeraire)
        self.fee = float(fee)

    @property
    def k(self) -> float:
        return self.x * self.y

    def spot_price(self) -> float:
        """Marginal price of X in units of Y:  p = y / x."""
        return self.y / self.x

    def amount_out(self, dx: float) -> float:
        """Output dy for an input dx of X (fee taken on the input).

        dy = (1-f) * y * dx / (x + (1-f) * dx)
        """
        g = 1.0 - self.fee
        return g * self.y * dx / (self.x + g * dx)

    def price_impact(self, dx: float) -> float:
        """Relative slippage = realized price / spot price - 1 (X -> Y trade)."""
        dy = self.amount_out(dx)
        realized = dy / dx                       # Y received per X sold
        return realized / self.spot_price() - 1.0


# --------------------------------------------------------------------------
# Stable-Swap (Curve), n = 2 coins
# Invariant (whitepaper form, A = amplification, n = 2, n^n = 4):
#     4A (x + y) + D = 4A D + D^3 / (4 x y)
# --------------------------------------------------------------------------
class StableSwap:
    def __init__(self, x: float, y: float, A: float = 100.0, fee: float = 0.0004):
        self.x = float(x)
        self.y = float(y)
        self.A = float(A)
        self.fee = float(fee)
        self.n = 2

    def _invariant_residual(self, D: float, x: float, y: float) -> float:
        Ann = self.A * self.n ** self.n          # = 4A for n = 2
        return Ann * (x + y) + D - (Ann * D + D ** 3 / (self.n ** self.n * x * y))

    def D(self, x: float | None = None, y: float | None = None) -> float:
        x = self.x if x is None else x
        y = self.y if y is None else y
        s = x + y
        # D lies in (0, s]; brentq on the invariant residual as a function of D.
        lo, hi = 1e-12, s * 2.0
        return brentq(lambda D: self._invariant_residual(D, x, y), lo, hi, xtol=1e-12, rtol=1e-12)

    def _y_given_x(self, x_new: float, D: float) -> float:
        """Solve invariant for y given x_new and fixed D.

        As y -> 0+ the residual -> -inf and as y -> +inf it -> +inf, so a root
        always exists; for very small x_new the root can exceed D, so the upper
        bracket is grown until the sign flips.
        """
        f = lambda y: self._invariant_residual(D, x_new, y)
        lo = 1e-12
        hi = D
        flo = f(lo)
        for _ in range(60):
            if flo * f(hi) < 0:
                break
            hi *= 2.0
        return brentq(f, lo, hi, xtol=1e-12, rtol=1e-12)

    def spot_price(self) -> float:
        """Marginal price dp = -dy/dx via central finite difference."""
        D = self.D()
        eps = self.x * 1e-6
        y_plus = self._y_given_x(self.x + eps, D)
        y_minus = self._y_given_x(self.x - eps, D)
        return -(y_plus - y_minus) / (2 * eps)

    def amount_out(self, dx: float) -> float:
        D = self.D()
        x_new = self.x + (1.0 - self.fee) * dx
        y_new = self._y_given_x(x_new, D)
        return self.y - y_new

    def price_impact(self, dx: float) -> float:
        dy = self.amount_out(dx)
        realized = dy / dx
        return realized / self.spot_price() - 1.0


# --------------------------------------------------------------------------
# Weighted-Pool (Balancer):  V = x^{wx} * y^{wy},  wx + wy = 1
# --------------------------------------------------------------------------
class WeightedPool:
    def __init__(self, x: float, y: float, wx: float = 0.5, fee: float = 0.003):
        self.x = float(x)
        self.y = float(y)
        self.wx = float(wx)
        self.wy = 1.0 - float(wx)
        self.fee = float(fee)

    def spot_price(self) -> float:
        """Spot price of X in Y:  (x/wx) is balance/weight; SP = (y/wy)/(x/wx)."""
        return (self.y / self.wy) / (self.x / self.wx)

    def amount_out(self, dx: float) -> float:
        """A_o = y * (1 - (x / (x + (1-f) dx))^{wx/wy})."""
        g = 1.0 - self.fee
        ratio = self.x / (self.x + g * dx)
        return self.y * (1.0 - ratio ** (self.wx / self.wy))

    def price_impact(self, dx: float) -> float:
        dy = self.amount_out(dx)
        realized = dy / dx
        return realized / self.spot_price() - 1.0


# --------------------------------------------------------------------------
# Impermanent-loss closed forms
# --------------------------------------------------------------------------
def il_constant_product(r: np.ndarray | float):
    """IL of a 50/50 constant-product pool as a function of price ratio r = P'/P.

    IL(r) = 2 sqrt(r) / (1 + r) - 1   (<= 0).
    """
    r = np.asarray(r, dtype=float)
    return 2 * np.sqrt(r) / (1 + r) - 1.0


def il_weighted(r: np.ndarray | float, wx: float):
    """IL of a Balancer two-asset pool with weight wx on the moving asset X.

    value_pool / value_hold = (r^{wx}) / (wx * r + (1 - wx)),  IL = that - 1.
    (Asset Y is the numeraire, so only X's price moves by factor r.)
    """
    r = np.asarray(r, dtype=float)
    return r ** wx / (wx * r + (1 - wx)) - 1.0


def il_v3_range(r: np.ndarray | float, price_low: float, price_high: float):
    """Approximate IL of a Uniswap V3 position concentrated in [p_low, p_high].

    Within the range the position behaves like a constant-product pool with
    virtual reserves, so its IL is the V2 IL scaled by the concentration factor
    1 / (1 - (p_low/p_high)^{1/4}); outside the range the position is fully in
    one asset and IL saturates.  This returns the standard closed form derived
    from the V3 whitepaper value function (numeraire = Y, only X moves).
    """
    r = np.asarray(r, dtype=float)
    pa, pb = price_low, price_high
    sa, sb = np.sqrt(pa), np.sqrt(pb)

    def value_ratio(rr):
        # Current price P' = P0 * rr, with P0 = 1 (numeraire units).
        P = rr
        Pc = np.clip(P, pa, pb)
        sp = np.sqrt(Pc)
        # Position value in Y (L = 1): x*P + y with the V3 reserve formulas.
        x = (1.0 / sp - 1.0 / sb)
        y = (sp - sa)
        v_pool = x * P + y
        # Hold value: the assets you deposited at P0 = 1, held.
        sp0 = np.sqrt(np.clip(1.0, pa, pb))
        x0 = (1.0 / sp0 - 1.0 / sb)
        y0 = (sp0 - sa)
        v_hold = x0 * P + y0
        return v_pool / v_hold

    return np.vectorize(value_ratio)(r) - 1.0


# --------------------------------------------------------------------------
# Uniswap V3 capital efficiency
# --------------------------------------------------------------------------
def v3_capital_efficiency(price_low: float, price_high: float, p: float = 1.0) -> float:
    """Capital-efficiency multiplier of a V3 range [p_low, p_high] vs full-range V2.

    Multiplier ~ 1 / (1 - (p_low / p_high)^{1/4}) for a position centred near p.
    """
    return 1.0 / (1.0 - (price_low / price_high) ** 0.25)


if __name__ == "__main__":
    # quick self-checks
    cp = ConstantProduct(1000, 1000)
    print("CP spot:", cp.spot_price(), "out for 100:", cp.amount_out(100))
    ss = StableSwap(1000, 1000, A=100)
    print("SS D:", ss.D(), "spot:", ss.spot_price(), "out for 100:", ss.amount_out(100))
    wp = WeightedPool(1000, 1000, wx=0.8)
    print("WP spot:", wp.spot_price(), "out for 100:", wp.amount_out(100))
    print("IL cp at r=2:", il_constant_product(2.0))
    print("IL 80/20 at r=2:", il_weighted(2.0, 0.8))
    print("V3 cap-eff [0.9,1.1]:", v3_capital_efficiency(0.9, 1.1))
