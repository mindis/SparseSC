""" 
Utility methods for penalty parameters
"""

from SparseSC.fit_loo import loo_v_matrix
from SparseSC.fit_ct import ct_v_matrix
from SparseSC.fit_fold import fold_v_matrix

# from SparseSC.optimizers.cd_line_search import cdl_search
import numpy as np

_GRADIENT_MESSAGE = "Calculating maximum covariate penalty (i.e. the gradient at zero)"


def w_pen_guestimate(X):
    """ 
    A rule of thumb based on pure intuition which happens to work well on the
    examples we've tested.
    """
    return np.mean(np.var(X, axis=0))


def get_max_w_pen(X,Y,v_pen,**kwargs):
    """ 
    Calculates maximum value of w_pen for which the elements of tensor
    matrix (V) are not all zero conditional on the provided v_pen

    Relies on the fact that conditional on the data `v_pen * w_pen` is constant
    """
    return get_max_v_pen(X,Y,w_pen=1,**kwargs) / v_pen

def get_max_v_pen(X, Y, w_pen=None, X_treat=None, Y_treat=None, **kwargs):
    """ 
    Calculates maximum value of v_pen for which the elements of tensor
    matrix (V) are not all zero conditional on the provided w_pen.  If w_pen is
    not provided, a guestimate is used.

    Provides a unified wrapper to the various *_v_matrix functions, passing the
    parameter ``return_max_v_pen = True`` in order to obtain the gradient
    instead of he matrix
    """

    # PARAMETER QC
    try:
        X = np.asmatrix(X)
    except ValueError:
        raise ValueError("X is not coercible to a matrix")
    try:
        Y = np.asmatrix(Y)
    except ValueError:
        raise ValueError("Y is not coercible to a matrix")
    if (X_treat is None) != (Y_treat is None):
        raise ValueError(
            "parameters `X_treat` and `Y_treat` must both be Matrices or None"
        )
    if X.shape[1] == 0:
        raise ValueError("X.shape[1] == 0")
    if Y.shape[1] == 0:
        raise ValueError("Y.shape[1] == 0")
    if X.shape[0] != Y.shape[0]:
        raise ValueError(
            "X and Y have different number of rows (%s and %s)"
            % (X.shape[0], Y.shape[0])
        )
    if w_pen is None:
        w_pen = np.mean(np.var(X, axis=0))

    if X_treat is not None:

        # PARAMETER QC
        if not isinstance(X_treat, np.matrix):
            raise TypeError("X_treat is not a matrix")
        if not isinstance(Y_treat, np.matrix):
            raise TypeError("Y_treat is not a matrix")
        if X_treat.shape[1] == 0:
            raise ValueError("X_treat.shape[1] == 0")
        if Y_treat.shape[1] == 0:
            raise ValueError("Y_treat.shape[1] == 0")
        if X_treat.shape[0] != Y_treat.shape[0]:
            raise ValueError(
                "X_treat and Y_treat have different number of rows (%s and %s)"
                % (X.shape[0], Y.shape[0])
            )

        control_units = np.arange(X.shape[0])
        treated_units = np.arange(X.shape[0], X.shape[0] + X_treat.shape[0])

        try:
            _v_pen = iter(w_pen)
        except TypeError:
            # w_pen is a single value
            return ct_v_matrix(
                X=np.vstack((X, X_treat)),
                Y=np.vstack((Y, Y_treat)),
                w_pen=w_pen,
                control_units=control_units,
                treated_units=treated_units,
                return_max_v_pen=True,
                gradient_message=_GRADIENT_MESSAGE,
                **kwargs
            )

        else:
            # w_pen is an iterable of values
            return [
                ct_v_matrix(
                    X=np.vstack((X, X_treat)),
                    Y=np.vstack((Y, Y_treat)),
                    control_units=control_units,
                    treated_units=treated_units,
                    return_max_v_pen=True,
                    gradient_message=_GRADIENT_MESSAGE,
                    w_pen=_w_pen,
                    **kwargs
                )
                for _w_pen in w_pen
            ]

    else:

        try:
            _v_pen = iter(w_pen)
        except TypeError:
            if "grad_splits" in kwargs:
                # w_pen is a single value
                return fold_v_matrix(
                    X=X,
                    Y=Y,
                    w_pen=w_pen,
                    return_max_v_pen=True,
                    gradient_message=_GRADIENT_MESSAGE,
                    **kwargs
                )
            # w_pen is a single value
            try:
                return loo_v_matrix(
                    X=X,
                    Y=Y,
                    w_pen=w_pen,
                    return_max_v_pen=True,
                    gradient_message=_GRADIENT_MESSAGE,
                    **kwargs
                )
            except MemoryError:
                raise RuntimeError(
                    "MemoryError encountered.  Try setting `grad_splits` "
                    "parameter to reduce memory requirements."
                )  
        else:
            if "grad_splits" in kwargs:

                # w_pen is an iterable of values
                return [
                    fold_v_matrix(
                        X=X,
                        Y=Y,
                        w_pen=_w_pen,
                        return_max_v_pen=True,
                        gradient_message=_GRADIENT_MESSAGE,
                        **kwargs
                    )
                    for _w_pen in w_pen
                ]

            # w_pen is an iterable of values
            try:
                return [
                    loo_v_matrix(
                        X=X,
                        Y=Y,
                        w_pen=_w_pen,
                        return_max_v_pen=True,
                        gradient_message=_GRADIENT_MESSAGE,
                        **kwargs
                    )
                    for _w_pen in w_pen
                ]
            except MemoryError:
                raise RuntimeError(
                    "MemoryError encountered.  Try setting `grad_splits` "
                    "parameter to reduce memory requirements."
                )  
