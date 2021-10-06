"""Update a request"""

import logging
from django.utils import timezone
from ansible_catalog.main.approval.models import Request, Action
from ansible_catalog.main.approval.services.send_event import SendEvent
from ansible_catalog.main.approval.services.create_action import CreateAction

logger = logging.getLogger("approval")
AUTO_APPROVED_REASON = "Auto-approved"

class UpdateRequest:
    """Service class to update a request"""

    def __init__(self, request, options):
        self.request = (
            request
            if isinstance(request, Request)
            else Request.objects.get(id=request)
        )
        self.options = options

    def process(self):
        if self.options["state"] != self.request.state:
            logger.info(
                f"Changing request({self.request.id}) state from {self.request.state} to {self.options['state']}"
            )
            state = self.options["state"].lower()
            getattr(self, f"_{state}")()
        return self

    def _started(self):
        if self.request.is_leaf():
            self._run_request()

        self._persist_request()

        if self.request.is_root():
            SendEvent(self.request, SendEvent.EVENT_REQUEST_STARTED).process()

        if (
            self.request.is_child()
            and self.request.parent.state == Request.State.PENDING
        ):
            self._update_parent()

        if self._should_auto_approve():
            self._notify_request()

    def _notified(self):
        self._persist_request("notified_at")

        # if self.request.is_leaf():
        #    SendEvent(self.request, SendEvent.EVENT_GROUP_NOTIFIED) # Event not yet exist

        if self.request.is_child() and not self.request.parent.has_finished():
            self._update_parent()

        if self._should_auto_approve():
            self._approve_request()

    # Called directly when it is a leaf node, or indirectly from its child node
    def _completed(self):
        if self.request.is_leaf():
            self._finish_request()

        if self.request.state == Request.State.CANCELED:
            return

        if self.request.is_child():
            self._child_completed()
            return

        if self._request_is_completed():
            self._parent_completed()

    def _failed(self):
        self._completed()

    # Root only.
    def _canceled(self):
        self._skip_leaves()
        # self.request.random_access_keys.destroy_all # TODO

        self._persist_request("finished_at")
        SendEvent(self.request, SendEvent.EVENT_REQUEST_CANCELED).process()

    # Leaf only. skipped is caused by cancel or deny. This state will not propagate to root
    def _skipped(self):
        self._persist_request("finished_at")
        self.request.parent.invalidate_number_of_finished_children()

    def _skip_leaves(self):
        for leaf in self._leaves():
            if leaf.state == Request.State.PENDING:
                CreateAction(
                    leaf.id, {"operation": Action.Operation.SKIP, "user": None}
                ).process()

    def _child_completed(self):
        # request.random_access_keys.destroy_all # TODO
        self._persist_request("finished_at")
        # SendEvent(self.request, SendEvent.EVENT_GROUP_FINISHED) # event not yet exist

        self.request.parent.invalidate_number_of_finished_children()
        self._update_parent()

        if self.options["decision"] in (
            Request.Decision.DENIED,
            Request.Decision.ERROR,
        ):
            self._skip_leaves()
        elif self._peers_approved():
            self._start_next_leaves()

    # parent or standalone
    def _parent_completed(self):
        # request.random_access_keys.destroy_all # TODO
        self._persist_request("finished_at")

        # if request.is_leaf():
        # SendEvent(self.request, SendEvent.Event_GROUP_FINISHED) # event not yet exist

        SendEvent(self.request, SendEvent.EVENT_REQUEST_FINISHED).process()

    # A composite request
    def _request_is_completed(self):
        return (
            self.request.number_of_finished_children
            == self.request.number_of_children
            or self.options["decision"]
            in (Request.Decision.DENIED, Request.Decision.ERROR)
        )

    # Have all peers approved the request?
    def _peers_approved(self):
        peers = Request.objects.filter(
            workflow=self.request.workflow, parent=self.request.parent
        )
        for peer in peers:
            if not peer.decision == Request.Decision.APPROVED:
                return False
        return True

    def _start_next_leaves(self):
        for leaf in self._next_pending_leaves():
            CreateAction(
                leaf, {"operation": Action.Operation.START, "user": None}
            ).process()

    def _leaves(self):
        return Request.objects.filter(parent=self.request.root()).order_by(
            "id"
        )

    def _next_pending_leaves(self):
        peers = []
        for leaf in self._leaves():
            if leaf.state == Request.State.PENDING:
                if not peers or leaf.workflow_id == peers[0].workflow_id:
                    peers.append(leaf)
        return peers

    def _update_parent(self):
        self.__class__(self.request.parent, self.options).process()

    # start the external approval process if configured
    def _run_request(self):
        pass

    def _notify_request(self):
        # notify if this is an internal processing
        CreateAction(
            self.request, {"operation": Action.Operation.NOTIFY, "user": None}
        ).process()

    def _approve_request(self):
        # auto approve the request
        CreateAction(
            self.request, {"operation": Action.Operation.APPROVE, "user": None, "reason": AUTO_APPROVED_REASON}
        ).process()

    # complete the external approval process if configured
    def _finish_request(self):
        pass

    def _persist_request(self, time_field=None):
        if time_field:
            self.options[time_field] = timezone.now()
        Request.objects.filter(id=self.request.id).update(**self.options)
        self.request.refresh_from_db()

    def _should_auto_approve(self):
        if self.request.is_parent():
            return False
        if self.request.workflow is None or len(self.request.workflow.group_refs) == 0:
            return True
        return False
