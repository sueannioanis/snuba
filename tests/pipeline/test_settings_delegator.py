from typing import Sequence, Type, Union

import pytest

from snuba.pipeline.settings_delegator import RateLimiterDelegate
from snuba.request.request_settings import (
    HTTPRequestSettings,
    SubscriptionRequestSettings,
)
from snuba.state.rate_limit import RateLimitParameters

test_cases = [
    pytest.param(
        HTTPRequestSettings,
        [
            RateLimitParameters(
                rate_limit_name="rate_name",
                bucket="secondary_project",
                per_second_limit=10.0,
                concurrent_limit=22,
            ),
            RateLimitParameters(
                rate_limit_name="second_rate_name",
                bucket="secondary_table",
                per_second_limit=11.0,
                concurrent_limit=23,
            ),
        ],
        id="HTTP Request Settings",
    ),
    pytest.param(SubscriptionRequestSettings, [], id="Subscriptions request settings"),
]


@pytest.mark.parametrize("settings_class, expected_rate_limiters", test_cases)
def test_delegate(
    settings_class: Type[Union[HTTPRequestSettings, SubscriptionRequestSettings]],
    expected_rate_limiters: Sequence[RateLimitParameters],
) -> None:
    settings = settings_class(
        referrer="test",
        consistent=False,
        parent_api="parent",
        team="team",
        feature="feature",
    )

    settings.add_rate_limit(
        RateLimitParameters(
            rate_limit_name="rate_name",
            bucket="project",
            per_second_limit=10.0,
            concurrent_limit=22,
        )
    )

    settings_delegate = RateLimiterDelegate("secondary", settings)
    settings_delegate.add_rate_limit(
        RateLimitParameters(
            rate_limit_name="second_rate_name",
            bucket="table",
            per_second_limit=11.0,
            concurrent_limit=23,
        )
    )

    assert settings_delegate.referrer == settings.referrer
    assert settings_delegate.get_rate_limit_params() == expected_rate_limiters
