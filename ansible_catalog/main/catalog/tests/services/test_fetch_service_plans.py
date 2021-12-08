""" Test population json template with input parameters """
import pytest
import json

from ansible_catalog.main.catalog.tests.factories import (
    PortfolioItemFactory,
    CatalogServicePlanFactory,
)
from ansible_catalog.main.inventory.tests.factories import (
    ServiceOfferingFactory,
    InventoryServicePlanFactory,
)
from ansible_catalog.main.catalog.services.fetch_service_plans import (
    FetchServicePlans,
)


@pytest.mark.django_db
def test_fetch_service_plans_from_remote_with_enabled_survey():
    service_offering = ServiceOfferingFactory(survey_enabled=True)
    portfolio_item = PortfolioItemFactory(
        service_offering_ref=str(service_offering.id)
    )
    schema = {
        "schema_type": "default",
        "schema": {
            "fields": [
                {
                    "label": "Number of Job templates",
                    "name": "dev_null",
                    "initial_value": 8,
                    "helper_text": "Number of Job templates on this workflow",
                    "is_required": True,
                    "component": "text-field",
                    "type": "number",
                    "data_type": "integer",
                    "options": [{"label": "", "value": ""}],
                    "validate": [
                        {"type": "required-validator"},
                        {"type": "min-number-value", "value": 0},
                        {"type": "max-number-value", "value": 100},
                    ],
                }
            ],
            "title": "",
            "description": "",
        },
    }
    InventoryServicePlanFactory(
        service_offering=service_offering,
        create_json_schema=schema,
    )

    svc = FetchServicePlans(portfolio_item)
    svc.process()

    assert len(svc.service_plans) == 1
    assert svc.service_plans[0].portfolio_item_id == portfolio_item.id
    assert svc.service_plans[0].service_offering_ref == str(
        service_offering.id
    )
    assert svc.service_plans[0].schema == schema
    assert svc.service_plans[0].imported is False


@pytest.mark.django_db
def test_fetch_service_plans_from_remote_with_disabled_survey():
    service_offering = ServiceOfferingFactory()
    portfolio_item = PortfolioItemFactory(
        service_offering_ref=str(service_offering.id)
    )

    InventoryServicePlanFactory(
        service_offering=service_offering,
    )

    svc = FetchServicePlans(portfolio_item)
    svc.process()

    assert len(svc.service_plans) == 1
    assert svc.service_plans[0].portfolio_item_id == portfolio_item.id
    assert svc.service_plans[0].service_offering_ref == str(
        service_offering.id
    )
    assert svc.service_plans[0].schema["schemaType"] == "emptySchema"
    assert svc.service_plans[0].imported is False


@pytest.mark.django_db
def test_fetch_service_plans_from_local():
    service_offering = ServiceOfferingFactory()
    portfolio_item = PortfolioItemFactory(
        service_offering_ref=str(service_offering.id)
    )
    service_plan = CatalogServicePlanFactory(
        portfolio_item=portfolio_item,
    )
    ServicePlanFactory(
        service_offering=service_offering,
    )
    svc = FetchServicePlans(portfolio_item)
    svc.process()

    assert len(svc.service_plans) == 1
    assert svc.service_plans[0].portfolio_item_id == portfolio_item.id
    assert svc.service_plans[0].name == service_plan.name
    assert svc.service_plans[0].schema is None
    assert svc.service_plans[0].imported is True
    assert svc.service_plans[0].modified is False


@pytest.mark.django_db
def test_fetch_service_plans_force_from_remote():
    service_offering = ServiceOfferingFactory()
    portfolio_item = PortfolioItemFactory(
        service_offering_ref=str(service_offering.id)
    )
    CatalogServicePlanFactory(
        portfolio_item=portfolio_item,
    )
    ServicePlanFactory(
        service_offering=service_offering,
    )

    svc = FetchServicePlans(portfolio_item, force_remote=True)
    svc.process()

    assert len(svc.service_plans) == 1
    assert svc.service_plans[0].portfolio_item_id == portfolio_item.id
    assert svc.service_plans[0].service_offering_ref == str(
        service_offering.id
    )
    assert svc.service_plans[0].imported is False
