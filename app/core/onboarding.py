"""The Getting Started onboarding checklist view-model (Slice 5.3, #56).

Turns the three onboarding booleans on the user record into an ordered list of steps the
dashboard renders. Kept as a pure helper (no DB, no request) so the ordering, links, and
done-state logic are unit-testable independently of the page.
"""

from dataclasses import dataclass

from app.models.user import User


@dataclass(frozen=True)
class OnboardingStep:
    """A single Getting Started step: its label, the page it links to, and whether it's done."""

    label: str
    url: str
    done: bool


def build_onboarding_steps(user: User) -> list[OnboardingStep]:
    """The three onboarding steps in their documented order, with each step's done state.

    Order (Connect Storage → Set Notification Preferences → Upload First File) and target pages
    are fixed per issue #56. `onboarding_notifications_done` is flipped by Slice 7 (notifications,
    not built yet), so that step simply stays incomplete until then — no blocker.
    """
    return [
        OnboardingStep("Connect Storage", "/settings", user.onboarding_storage_done),
        OnboardingStep(
            "Set Notification Preferences", "/profile", user.onboarding_notifications_done
        ),
        OnboardingStep("Upload First File", "/upload", user.onboarding_first_upload_done),
    ]


def onboarding_complete(user: User) -> bool:
    """True once every onboarding step is done — the checklist is hidden entirely at that point."""
    return all(step.done for step in build_onboarding_steps(user))
