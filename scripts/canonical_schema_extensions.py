#!/usr/bin/env python3
"""
Canonical schema extensions for the homeowners policy_check schema.

``config/policy_check/homeowners.json`` is generated from the supplied
homeowners.schema.json (v1.4.0). A review of the 69 homeowners reference
documents in ``Data/original PDFs`` found fields, sections and printed labels
the supplied skeleton did not carry. This module re-applies all of them, so a
regenerated base schema comes back to the reviewed one:

    python scripts/canonical_schema_extensions.py            apply, in place
    python scripts/canonical_schema_extensions.py --check    exit 1 if applying would change the file

It is idempotent - applying it to an already-extended file changes nothing:

1. ``ADDED``     new fields, sections and lists (path, kind), in document order;
2. ``MERGED``    duplicate fields removed; their labels live on the kept field;
3. ``ALIASES``   the printed labels ("fideon:aliases") of every field this
                 review touched; ``ALIASES_REMOVED`` labels moved off a field
                 because they pointed at the wrong meaning;
4. every field gets ``fideon:value_type`` and a generated ``description``,
   every section and list a ``description``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "config" / "policy_check" / "homeowners.json"
REF = {"$ref": "#/$defs/FieldValue"}

# ── 1. added fields, sections and lists ─────────────────────────────────────
# kind: field | object | list_obj (list of objects) | list_scalar (list of FieldValue)
ADDED = [('document.document_form_number', 'field'),
 ('document.document_form_edition', 'field'),
 ('document.transaction_code', 'field'),
 ('document.transaction_expiration_date', 'field'),
 ('document.term_sequence', 'field'),
 ('document.mailed_date', 'field'),
 ('document.print_time', 'field'),
 ('document.print_routing_code', 'field'),
 ('document.operator_initials', 'field'),
 ('document.document_control_code', 'field'),
 ('document.barcode_data', 'field'),
 ('document.remarks', 'field'),
 ('document.total_locations', 'field'),
 ('document.mail_to', 'object'),
 ('document.mail_to.name', 'field'),
 ('document.mail_to.producer_code', 'field'),
 ('document.mail_to.address', 'object'),
 ('document.mail_to.address.line_1', 'field'),
 ('document.mail_to.address.line_2', 'field'),
 ('document.mail_to.address.city', 'field'),
 ('document.mail_to.address.state', 'field'),
 ('document.mail_to.address.postal_code', 'field'),
 ('document.mail_to.address.county', 'field'),
 ('document.mail_to.address.country', 'field'),
 ('document.mail_to.address.county_code', 'field'),
 ('document.changes', 'list_obj'),
 ('document.changes[].effective_date', 'field'),
 ('document.changes[].location_reference', 'field'),
 ('document.changes[].field_changed', 'field'),
 ('document.changes[].old_value', 'field'),
 ('document.changes[].new_value', 'field'),
 ('document.changes[].description', 'field'),
 ('document.changes[].detail_on_declarations_indicator', 'field'),
 ('document.package_index', 'list_obj'),
 ('document.package_index[].form_number', 'field'),
 ('document.package_index[].edition_date', 'field'),
 ('document.package_index[].form_title', 'field'),
 ('document.package_index[].index_section', 'field'),
 ('document.package_index[].page_reference', 'field'),
 ('document.package_index[].state', 'field'),
 ('document.esignature_certificate', 'object'),
 ('document.esignature_certificate.document_reference', 'field'),
 ('document.esignature_certificate.document_title', 'field'),
 ('document.esignature_certificate.document_region', 'field'),
 ('document.esignature_certificate.sender_name', 'field'),
 ('document.esignature_certificate.sender_email', 'field'),
 ('document.esignature_certificate.total_pages', 'field'),
 ('document.esignature_certificate.secondary_security', 'field'),
 ('document.esignature_certificate.participants', 'list_obj'),
 ('document.esignature_certificate.participants[].name', 'field'),
 ('document.esignature_certificate.participants[].email', 'field'),
 ('document.esignature_certificate.participants[].role', 'field'),
 ('document.esignature_certificate.participants[].signed_datetime', 'field'),
 ('document.esignature_certificate.history', 'list_obj'),
 ('document.esignature_certificate.history[].timestamp', 'field'),
 ('document.esignature_certificate.history[].event_description', 'field'),
 ('document.esignature_certificate.history[].ip_address', 'field'),
 ('document.esignature_certificate.history[].user_agent', 'field'),
 ('document.esignature_certificate.attached_page_count', 'field'),
 ('document.esignature_certificate.provider', 'field'),
 ('document.not_a_bill_indicator', 'field'),
 ('document.letter_signatory', 'object'),
 ('document.letter_signatory.name', 'field'),
 ('document.letter_signatory.title', 'field'),
 ('document.enclosures_requiring_action', 'list_scalar'),
 ('document.page_number', 'field'),
 ('carrier.state_of_incorporation', 'field'),
 ('carrier.surplus_lines_broker_address', 'object'),
 ('carrier.surplus_lines_broker_address.line_1', 'field'),
 ('carrier.surplus_lines_broker_address.line_2', 'field'),
 ('carrier.surplus_lines_broker_address.city', 'field'),
 ('carrier.surplus_lines_broker_address.state', 'field'),
 ('carrier.surplus_lines_broker_address.postal_code', 'field'),
 ('carrier.surplus_lines_broker_address.county', 'field'),
 ('carrier.surplus_lines_broker_address.country', 'field'),
 ('carrier.surplus_lines_broker_address.county_code', 'field'),
 ('carrier.surplus_lines_filing', 'object'),
 ('carrier.surplus_lines_filing.association_name', 'field'),
 ('carrier.surplus_lines_filing.received_date', 'field'),
 ('carrier.surplus_lines_filing.document_id', 'field'),
 ('carrier.program_administrator', 'object'),
 ('carrier.program_administrator.name', 'field'),
 ('carrier.program_administrator.address', 'object'),
 ('carrier.program_administrator.address.line_1', 'field'),
 ('carrier.program_administrator.address.line_2', 'field'),
 ('carrier.program_administrator.address.city', 'field'),
 ('carrier.program_administrator.address.state', 'field'),
 ('carrier.program_administrator.address.postal_code', 'field'),
 ('carrier.program_administrator.address.county', 'field'),
 ('carrier.program_administrator.address.country', 'field'),
 ('carrier.program_administrator.address.county_code', 'field'),
 ('carrier.program_administrator.phone', 'field'),
 ('carrier.program_administrator.email', 'field'),
 ('carrier.program_administrator.website', 'field'),
 ('carrier.additional_contacts', 'list_obj'),
 ('carrier.additional_contacts[].purpose', 'field'),
 ('carrier.additional_contacts[].phone', 'field'),
 ('carrier.additional_contacts[].fax', 'field'),
 ('carrier.additional_contacts[].email', 'field'),
 ('carrier.additional_contacts[].website', 'field'),
 ('carrier.additional_contacts[].hours', 'field'),
 ('carrier.additional_contacts[].contact_name', 'field'),
 ('carrier.additional_contacts[].department', 'field'),
 ('carrier.additional_contacts[].address', 'object'),
 ('carrier.additional_contacts[].address.line_1', 'field'),
 ('carrier.additional_contacts[].address.line_2', 'field'),
 ('carrier.additional_contacts[].address.city', 'field'),
 ('carrier.additional_contacts[].address.state', 'field'),
 ('carrier.additional_contacts[].address.postal_code', 'field'),
 ('carrier.additional_contacts[].address.county', 'field'),
 ('carrier.additional_contacts[].address.country', 'field'),
 ('carrier.additional_contacts[].address.county_code', 'field'),
 ('carrier.fiscal_year_period', 'field'),
 ('carrier.annual_meeting_schedule', 'field'),
 ('carrier.bylaws', 'object'),
 ('carrier.bylaws.form_reference', 'field'),
 ('carrier.bylaws.board_size_min', 'field'),
 ('carrier.bylaws.board_size_max', 'field'),
 ('carrier.bylaws.director_term_years', 'field'),
 ('carrier.bylaws.annual_meeting_notice_days', 'field'),
 ('carrier.bylaws.nomination_notice_days', 'field'),
 ('carrier.bylaws.quorum', 'field'),
 ('carrier.bylaws.notes', 'field'),
 ('carrier.bylaws.special_meeting_notice_days', 'field'),
 ('carrier.bylaws.board_meeting_notice_days', 'field'),
 ('carrier.bylaws.min_additional_board_meetings', 'field'),
 ('carrier.bylaws.board_meeting_call_min_directors', 'field'),
 ('carrier.bylaws.executive_committee_min_size', 'field'),
 ('carrier.bylaws.executive_committee_term_years', 'field'),
 ('carrier.bylaws.officer_term_years', 'field'),
 ('carrier.bylaws.removal_vote_fraction', 'field'),
 ('carrier.bylaws.additional_nominee_min_members', 'field'),
 ('carrier.bylaws.indemnification_notice_days', 'field'),
 ('carrier.bylaws.amendment_submission_days', 'field'),
 ('carrier.bylaws.statutory_basis', 'field'),
 ('producer.producer_sub_code', 'field'),
 ('producer.territory', 'field'),
 ('producer.paperless_indicator', 'field'),
 ('producer.direct_mail_indicator', 'field'),
 ('producer.producer_contact_phone', 'field'),
 ('producer.producer_contact_email', 'field'),
 ('policy.original_inception_date', 'field'),
 ('policy.is_continuous_renewal', 'field'),
 ('policy.minimum_earned_premium_amount', 'field'),
 ('policy.minimum_refund_amount', 'field'),
 ('policy.service_of_suit_designee', 'field'),
 ('policy.required_policy_period_years', 'field'),
 ('policy.suit_limitation_period', 'field'),
 ('policy.cancellation_notice_terms', 'list_obj'),
 ('policy.cancellation_notice_terms[].reason', 'field'),
 ('policy.cancellation_notice_terms[].notice_days', 'field'),
 ('policy.cancellation_notice_terms[].notice_days_max', 'field'),
 ('policy.cancellation_notice_terms[].notes', 'field'),
 ('policy.assessment_contingent_liability_multiple', 'field'),
 ('policy.assessment_penalty_percentage', 'field'),
 ('policy.liberalization_period_days', 'field'),
 ('policy.assessment_notice_days', 'field'),
 ('policy.assessment_payment_period_min_days', 'field'),
 ('policy.assessment_payment_period_max_days', 'field'),
 ('policy.assessment_collection_days', 'field'),
 ('policy.new_policy_period_days', 'field'),
 ('policy.cancellation_refund_method', 'field'),
 ('named_insured.contact.phones', 'list_obj'),
 ('named_insured.contact.phones[].phone_type', 'field'),
 ('named_insured.contact.phones[].number', 'field'),
 ('named_insured.contact.phones[].is_primary', 'field'),
 ('named_insured.contact.phones[].contact_name', 'field'),
 ('named_insured.name_as_printed', 'field'),
 ('named_insured.delivery_preference', 'field'),
 ('named_insured.individuals', 'list_obj'),
 ('named_insured.individuals[].name', 'field'),
 ('named_insured.individuals[].insured_type', 'field'),
 ('named_insured.individuals[].role', 'field'),
 ('named_insured.individuals[].relationship', 'field'),
 ('named_insured.individuals[].date_of_birth', 'field'),
 ('named_insured.individuals[].marital_status', 'field'),
 ('named_insured.individuals[].gender', 'field'),
 ('named_insured.individuals[].ssn_masked', 'field'),
 ('named_insured.individuals[].occupation', 'field'),
 ('named_insured.individuals[].employment_status', 'field'),
 ('named_insured.individuals[].business_on_premises', 'field'),
 ('named_insured.third_party_designee', 'object'),
 ('named_insured.third_party_designee.name', 'field'),
 ('named_insured.third_party_designee.address', 'object'),
 ('named_insured.third_party_designee.address.line_1', 'field'),
 ('named_insured.third_party_designee.address.line_2', 'field'),
 ('named_insured.third_party_designee.address.city', 'field'),
 ('named_insured.third_party_designee.address.state', 'field'),
 ('named_insured.third_party_designee.address.postal_code', 'field'),
 ('named_insured.third_party_designee.address.county', 'field'),
 ('named_insured.third_party_designee.address.country', 'field'),
 ('named_insured.third_party_designee.address.county_code', 'field'),
 ('named_insured.third_party_designee.email', 'field'),
 ('named_insured.third_party_designee.policy_type', 'field'),
 ('named_insured.third_party_designee.insured_signature_date', 'field'),
 ('named_insured.third_party_designee.designee_signature_date', 'field'),
 ('named_insured.third_party_designee.eligibility_age', 'field'),
 ('named_insured.third_party_designee.designation_effective_business_days', 'field'),
 ('named_insured.third_party_designee.return_instructions', 'object'),
 ('named_insured.third_party_designee.return_instructions.name', 'field'),
 ('named_insured.third_party_designee.return_instructions.address', 'object'),
 ('named_insured.third_party_designee.return_instructions.address.line_1', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.line_2', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.city', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.state', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.postal_code', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.county', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.country', 'field'),
 ('named_insured.third_party_designee.return_instructions.address.county_code', 'field'),
 ('named_insured.third_party_designee.return_instructions.email', 'field'),
 ('named_insured.third_party_designee.return_instructions.fax', 'field'),
 ('named_insured.third_party_designee.return_instructions.required_mail_method', 'field'),
 ('named_insured.third_party_designee.insured_date_of_birth', 'field'),
 ('named_insured.insured_definition_age_limits', 'object'),
 ('named_insured.insured_definition_age_limits.student_age_limit_relative', 'field'),
 ('named_insured.insured_definition_age_limits.student_age_limit_other', 'field'),
 ('named_insured.insured_definition_age_limits.student_theft_residence_days', 'field'),
 ('named_insured.insured_definition_age_limits.max_roomers_boarders', 'field'),
 ('named_insured.insured_definition_age_limits.dependent_in_care_age_limit', 'field'),
 ('locations[].address.municipality', 'field'),
 ('locations[].address.sub_county', 'field'),
 ('locations[].legal_description', 'field'),
 ('interested_parties[].party_id', 'field'),
 ('interested_parties[].status', 'field'),
 ('interested_parties[].form_reference', 'field'),
 ('interested_parties[].location_reference', 'field'),
 ('interested_parties[].applicable_coverages', 'list_scalar'),
 ('interested_parties[].other_coverages_specified', 'field'),
 ('interested_parties[].cancellation_notice_days', 'field'),
 ('interested_parties[].mailing_address', 'object'),
 ('interested_parties[].mailing_address.line_1', 'field'),
 ('interested_parties[].mailing_address.line_2', 'field'),
 ('interested_parties[].mailing_address.city', 'field'),
 ('interested_parties[].mailing_address.state', 'field'),
 ('interested_parties[].mailing_address.postal_code', 'field'),
 ('interested_parties[].mailing_address.county', 'field'),
 ('interested_parties[].mailing_address.country', 'field'),
 ('interested_parties[].mailing_address.county_code', 'field'),
 ('premium.premium_by_coverage_part[].applies_to', 'field'),
 ('premium.premium_by_coverage_part[].location_reference', 'field'),
 ('premium.premium_by_coverage_part[].property_covered', 'field'),
 ('premium.premium_by_coverage_part[].limit_amount', 'field'),
 ('premium.premium_by_coverage_part[].deductible_amount', 'field'),
 ('premium.premium_by_coverage_part[].is_included', 'field'),
 ('premium.coverage_premium', 'field'),
 ('premium.premium_before_discounts', 'field'),
 ('premium.total_discount_amount', 'field'),
 ('premium.prior_annual_premium', 'field'),
 ('premium.annual_premium_change', 'field'),
 ('premium.pro_rata_premium_change', 'field'),
 ('premium.premium_adjustment_method', 'field'),
 ('premium.broker_fee', 'field'),
 ('premium.number_of_risks', 'field'),
 ('premium.total_fees_amount', 'field'),
 ('billing.checks_payable_to', 'field'),
 ('billing.remittance_address', 'object'),
 ('billing.remittance_address.line_1', 'field'),
 ('billing.remittance_address.line_2', 'field'),
 ('billing.remittance_address.city', 'field'),
 ('billing.remittance_address.state', 'field'),
 ('billing.remittance_address.postal_code', 'field'),
 ('billing.remittance_address.county', 'field'),
 ('billing.remittance_address.country', 'field'),
 ('billing.remittance_address.county_code', 'field'),
 ('billing.invoice_date', 'field'),
 ('billing.amount_enclosed', 'field'),
 ('billing.scan_line', 'field'),
 ('billing.bank_account_type', 'field'),
 ('billing.bank_account_number_masked', 'field'),
 ('billing.preferred_due_day', 'field'),
 ('billing.payments', 'list_obj'),
 ('billing.payments[].payer_name', 'field'),
 ('billing.payments[].payer_address', 'object'),
 ('billing.payments[].payer_address.line_1', 'field'),
 ('billing.payments[].payer_address.line_2', 'field'),
 ('billing.payments[].payer_address.city', 'field'),
 ('billing.payments[].payer_address.state', 'field'),
 ('billing.payments[].payer_address.postal_code', 'field'),
 ('billing.payments[].payer_address.county', 'field'),
 ('billing.payments[].payer_address.country', 'field'),
 ('billing.payments[].payer_address.county_code', 'field'),
 ('billing.payments[].payment_type', 'field'),
 ('billing.payments[].account_number_masked', 'field'),
 ('billing.payments[].payment_status', 'field'),
 ('billing.payments[].payment_date', 'field'),
 ('billing.payments[].amount', 'field'),
 ('billing.payments[].period_start', 'field'),
 ('billing.payments[].period_end', 'field'),
 ('billing.payments[].insurer', 'field'),
 ('billing.payments[].authorization_text', 'field'),
 ('billing.payments[].account_holder_signature', 'field'),
 ('billing.fee_schedule', 'list_obj'),
 ('billing.fee_schedule[].fee_name', 'field'),
 ('billing.fee_schedule[].amount', 'field'),
 ('billing.fee_schedule[].basis', 'field'),
 ('billing.fee_schedule[].trigger', 'field'),
 ('billing.fee_schedule[].form_reference', 'field'),
 ('forms_and_endorsements[].state', 'field'),
 ('forms_and_endorsements[].page_reference', 'field'),
 ('forms_and_endorsements[].print_version_timestamp', 'field'),
 ('forms_and_endorsements[].details', 'field'),
 ('forms_and_endorsements[].applies_to_locations', 'list_scalar'),
 ('forms_and_endorsements[].copyright_notice', 'field'),
 ('forms_and_endorsements[].form_page_count', 'field'),
 ('forms_and_endorsements[].statutory_reference', 'field'),
 ('loss_history[].category', 'field'),
 ('loss_history[].loss_source', 'field'),
 ('loss_history[].points', 'field'),
 ('loss_history[].occurrence_count', 'field'),
 ('loss_history[].dispute_indicator', 'field'),
 ('loss_history[].catastrophe_indicator', 'field'),
 ('state_notices[].edition_date', 'field'),
 ('state_notices[].notice_category', 'field'),
 ('state_notices[].contact_phone', 'field'),
 ('state_notices[].contact_website', 'field'),
 ('state_notices[].civil_penalty_amount', 'field'),
 ('state_notices[].affiliate_names', 'list_scalar'),
 ('state_notices[].regulator_contact', 'object'),
 ('state_notices[].regulator_contact.name', 'field'),
 ('state_notices[].regulator_contact.phone', 'field'),
 ('state_notices[].regulator_contact.email', 'field'),
 ('state_notices[].regulator_contact.address', 'object'),
 ('state_notices[].regulator_contact.address.line_1', 'field'),
 ('state_notices[].regulator_contact.address.line_2', 'field'),
 ('state_notices[].regulator_contact.address.city', 'field'),
 ('state_notices[].regulator_contact.address.state', 'field'),
 ('state_notices[].regulator_contact.address.postal_code', 'field'),
 ('state_notices[].regulator_contact.address.county', 'field'),
 ('state_notices[].regulator_contact.address.country', 'field'),
 ('state_notices[].regulator_contact.address.county_code', 'field'),
 ('state_notices[].privacy_sharing_practices', 'list_obj'),
 ('state_notices[].privacy_sharing_practices[].reason', 'field'),
 ('state_notices[].privacy_sharing_practices[].company_shares', 'field'),
 ('state_notices[].privacy_sharing_practices[].can_limit', 'field'),
 ('state_notices[].peril_summary', 'list_obj'),
 ('state_notices[].peril_summary[].peril', 'field'),
 ('state_notices[].peril_summary[].is_covered', 'field'),
 ('state_notices[].loss_ratio_disclosure', 'field'),
 ('state_notices[].provided_by', 'list_scalar'),
 ('state_notices[].form_reference_edition', 'field'),
 ('state_notices[].copyright_notice', 'field'),
 ('claim_reporting.proof_of_loss_days', 'field'),
 ('claim_reporting.claim_payment_days', 'field'),
 ('claim_reporting.appraiser_selection_days', 'field'),
 ('claim_reporting.umpire_selection_days', 'field'),
 ('claim_reporting.repair_option_notice_days', 'field'),
 ('claim_reporting.tax_lien_payment_days', 'field'),
 ('claim_reporting.estimate_provision_days', 'field'),
 ('claim_reporting.liability_denial_action_days', 'field'),
 ('claim_reporting.judgment_payment_days', 'field'),
 ('claim_reporting.declaratory_action_days', 'field'),
 ('claim_reporting.suit_waiting_period_after_proof_days', 'field'),
 ('signature.officer_signatures', 'list_obj'),
 ('signature.officer_signatures[].company', 'field'),
 ('signature.officer_signatures[].name', 'field'),
 ('signature.officer_signatures[].title', 'field'),
 ('signature.party_signatures', 'list_obj'),
 ('signature.party_signatures[].role', 'field'),
 ('signature.party_signatures[].name', 'field'),
 ('signature.party_signatures[].signed_date', 'field'),
 ('signature.is_signed', 'field'),
 ('homeowners.dwelling.described_location.municipality', 'field'),
 ('homeowners.dwelling.described_location.sub_county', 'field'),
 ('homeowners.dwelling.acreage', 'field'),
 ('homeowners.dwelling.legal_description', 'field'),
 ('homeowners.dwelling.age_of_home', 'field'),
 ('homeowners.dwelling.years_owned', 'field'),
 ('homeowners.dwelling.purchase_price', 'field'),
 ('homeowners.dwelling.cost_of_improvements', 'field'),
 ('homeowners.dwelling.roof_year_installed', 'field'),
 ('homeowners.dwelling.roof_updated_within_20_years', 'field'),
 ('homeowners.dwelling.roof_shape', 'field'),
 ('homeowners.dwelling.roof_to_wall_attachment', 'field'),
 ('homeowners.dwelling.opening_protection', 'field'),
 ('homeowners.dwelling.heating_fuel_type', 'field'),
 ('homeowners.dwelling.heating_installation_year', 'field'),
 ('homeowners.dwelling.secondary_heating_type', 'field'),
 ('homeowners.dwelling.fuel_tank_location', 'field'),
 ('homeowners.dwelling.thermostat_controlled_central_heat', 'field'),
 ('homeowners.dwelling.electrical_service_type', 'field'),
 ('homeowners.dwelling.renovation', 'object'),
 ('homeowners.dwelling.renovation.heating_year', 'field'),
 ('homeowners.dwelling.renovation.roof_year', 'field'),
 ('homeowners.dwelling.renovation.plumbing_year', 'field'),
 ('homeowners.dwelling.renovation.electrical_year', 'field'),
 ('homeowners.dwelling.renovation.heating_updated', 'field'),
 ('homeowners.dwelling.renovation.roof_updated', 'field'),
 ('homeowners.dwelling.renovation.plumbing_updated', 'field'),
 ('homeowners.dwelling.renovation.electrical_updated', 'field'),
 ('homeowners.dwelling.exterior_wall_type', 'field'),
 ('homeowners.dwelling.number_of_bathrooms', 'field'),
 ('homeowners.dwelling.garage_type', 'field'),
 ('homeowners.dwelling.garage_number_of_cars', 'field'),
 ('homeowners.dwelling.number_of_units', 'field'),
 ('homeowners.dwelling.units_between_fire_walls', 'field'),
 ('homeowners.dwelling.townhouse_rowhouse_indicator', 'field'),
 ('homeowners.dwelling.doublewide_indicator', 'field'),
 ('homeowners.dwelling.lead_abatement', 'field'),
 ('homeowners.dwelling.certificate_of_occupancy_date', 'field'),
 ('homeowners.dwelling.gated_community', 'field'),
 ('homeowners.dwelling.visibility', 'field'),
 ('homeowners.dwelling.principal_unit_at_risk', 'field'),
 ('homeowners.dwelling.number_of_residence_employees', 'field'),
 ('homeowners.dwelling.is_currently_occupied', 'field'),
 ('homeowners.dwelling.occupied_by_others', 'field'),
 ('homeowners.dwelling.is_rented_to_others', 'field'),
 ('homeowners.dwelling.months_occupied_annually', 'field'),
 ('homeowners.dwelling.usage_explanation', 'field'),
 ('homeowners.dwelling.pipes_winterized', 'field'),
 ('homeowners.dwelling.accessible_year_round', 'field'),
 ('homeowners.dwelling.caretaker', 'object'),
 ('homeowners.dwelling.caretaker.has_caretaker', 'field'),
 ('homeowners.dwelling.caretaker.name', 'field'),
 ('homeowners.dwelling.waterfront_property', 'field'),
 ('homeowners.dwelling.water_exposures', 'list_scalar'),
 ('homeowners.dwelling.pool_features', 'list_scalar'),
 ('homeowners.dwelling.dogs_count', 'field'),
 ('homeowners.dwelling.dogs', 'list_obj'),
 ('homeowners.dwelling.dogs[].breed', 'field'),
 ('homeowners.dwelling.dogs[].description', 'field'),
 ('homeowners.dwelling.dogs[].bite_history', 'field'),
 ('homeowners.dwelling.dogs[].dog_number', 'field'),
 ('homeowners.dwelling.other_animals', 'list_scalar'),
 ('homeowners.dwelling.business_on_premises', 'field'),
 ('homeowners.dwelling.replacement_cost_estimator', 'field'),
 ('homeowners.dwelling.related_policy_number', 'field'),
 ('homeowners.dwelling.has_related_private_structures', 'field'),
 ('homeowners.dwelling.business_on_premises_description', 'field'),
 ('homeowners.dwelling.has_monitoring_system', 'field'),
 ('homeowners.dwelling.dogs_bite_history_any', 'field'),
 ('homeowners.dwelling.dog_bite_history_explanation', 'field'),
 ('homeowners.dwelling.secondary_heating_explanation', 'field'),
 ('homeowners.dwelling.roof_type_explanation', 'field'),
 ('homeowners.dwelling.slab_foundation', 'field'),
 ('homeowners.dwelling.territory_sub_code', 'field'),
 ('homeowners.dwelling.unoccupancy_threshold_days', 'field'),
 ('homeowners.dwelling.freeze_protection_min_temperature_f', 'field'),
 ('homeowners.dwelling.vacancy_thresholds', 'list_obj'),
 ('homeowners.dwelling.vacancy_thresholds[].peril', 'field'),
 ('homeowners.dwelling.vacancy_thresholds[].days', 'field'),
 ('homeowners.dwelling.vacancy_thresholds[].form_reference', 'field'),
 ('homeowners.dwelling.has_secondary_heating', 'field'),
 ('homeowners.dwelling.has_other_animals', 'field'),
 ('homeowners.dwelling.building_description', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].limit_percentage', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].limit_percentage_basis', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].minimum_amount', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].maximum_amount', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].limit_increase_amount', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].time_limit', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].decision_deadline_days', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].minimum_loss_threshold_amount', 'field'),
 ('homeowners.section_i_property_coverages.additional_coverages[].total_limit', 'field'),
 ('homeowners.section_i_property_coverages.coverage_a_dwelling_premium', 'field'),
 ('homeowners.section_i_property_coverages.coverage_b_other_structures_premium', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_personal_property_premium', 'field'),
 ('homeowners.section_i_property_coverages.coverage_d_loss_of_use_premium', 'field'),
 ('homeowners.section_i_property_coverages.coverage_a_coverage_tier', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_coverage_tier', 'field'),
 ('homeowners.section_i_property_coverages.personal_property_loss_settlement_basis', 'field'),
 ('homeowners.section_i_property_coverages.roof_surfacing_loss_settlement_basis', 'field'),
 ('homeowners.section_i_property_coverages.ordinance_or_law_limit', 'field'),
 ('homeowners.section_i_property_coverages.inflation_guard_period', 'field'),
 ('homeowners.section_i_property_coverages.inflation_guard_applies_to', 'list_scalar'),
 ('homeowners.section_i_property_coverages.replacement_cost_insurance_to_value_percentage', 'field'),
 ('homeowners.section_i_property_coverages.replacement_cost_holdback_threshold', 'field'),
 ('homeowners.section_i_property_coverages.replacement_cost_claim_period_days', 'field'),
 ('homeowners.section_i_property_coverages.renewal_modified_coverages', 'list_scalar'),
 ('homeowners.section_i_property_coverages.loss_assessment_additional_locations', 'list_obj'),
 ('homeowners.section_i_property_coverages.loss_assessment_additional_locations[].location', 'field'),
 ('homeowners.section_i_property_coverages.loss_assessment_additional_locations[].limit_amount', 'field'),
 ('homeowners.section_i_property_coverages.loss_assessment_additional_insurance_applies_to', 'field'),
 ('homeowners.section_i_property_coverages.coverage_b_percentage_of_coverage_a', 'field'),
 ('homeowners.section_i_property_coverages.coverage_d_civil_authority_period', 'field'),
 ('homeowners.section_i_property_coverages.volcanic_eruption_period_hours', 'field'),
 ('homeowners.section_i_property_coverages.inflation_guard_basis', 'field'),
 ('homeowners.section_i_property_coverages.additional_amount_improvement_notice_days', 'field'),
 ('homeowners.section_i_property_coverages.additional_amount_improvement_threshold_percentage', 'field'),
 ('homeowners.section_i_property_coverages.personal_property_replacement_cost_holdback_threshold', 'field'),
 ('homeowners.section_i_property_coverages.coverage_b_combination_threshold', 'field'),
 ('homeowners.section_i_property_coverages.tree_distance_limit_feet', 'field'),
 ('homeowners.section_i_property_coverages.farm_personal_property_scheduled_limit', 'field'),
 ('homeowners.section_i_property_coverages.farm_barns_buildings_structures_limit', 'field'),
 ('homeowners.section_i_property_coverages.loss_assessment_deductible_sublimit', 'field'),
 ('homeowners.section_i_property_coverages.loss_assessment_prior_loss_cap', 'field'),
 ('homeowners.section_i_property_coverages.earthquake_aftershock_period_hours', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_other_residences_percentage', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_other_residences_minimum', 'field'),
 ('homeowners.section_i_property_coverages.newly_acquired_residence_days', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_self_storage_percentage', 'field'),
 ('homeowners.section_i_property_coverages.coverage_c_self_storage_minimum', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].limit_percentage', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].limit_percentage_basis', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].minimum_amount', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].maximum_amount', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].limit_increase_amount', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].time_limit', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].decision_deadline_days', 'field'),
 ('homeowners.section_ii_liability_coverages.additional_coverages[].minimum_loss_threshold_amount', 'field'),
 ('homeowners.section_ii_liability_coverages.coverage_e_personal_liability_premium', 'field'),
 ('homeowners.section_ii_liability_coverages.coverage_f_medical_payments_premium', 'field'),
 ('homeowners.section_ii_liability_coverages.liability_coverage_type', 'field'),
 ('homeowners.section_ii_liability_coverages.coverage_e_limit_increase', 'field'),
 ('homeowners.section_ii_liability_coverages.coverage_f_limit_increase', 'field'),
 ('homeowners.section_ii_liability_coverages.damage_to_property_of_others_limit_increase', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures', 'list_obj'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].exposure_type', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].location', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].coverage', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].exposure_number', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address', 'object'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.line_1', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.line_2', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.city', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.state', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.postal_code', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.county', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.country', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].address.county_code', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].number_of_families', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].exposure_count', 'field'),
 ('homeowners.section_ii_liability_coverages.covered_exposures[].description', 'field'),
 ('homeowners.section_ii_liability_coverages.medical_expense_period_years', 'field'),
 ('homeowners.section_ii_liability_coverages.business_compensation_threshold', 'field'),
 ('homeowners.section_ii_liability_coverages.business_compensation_period_months', 'field'),
 ('homeowners.section_ii_liability_coverages.intentional_damage_min_age', 'field'),
 ('homeowners.section_ii_liability_coverages.excluded_animal_types', 'list_scalar'),
 ('homeowners.section_ii_liability_coverages.max_dogs_permitted', 'field'),
 ('homeowners.section_ii_liability_coverages.swimming_pool_fence_min_height_inches', 'field'),
 ('homeowners.section_ii_liability_coverages.domestic_employee_notice_months', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds', 'object'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.toy_vehicle_max_age', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.toy_vehicle_max_mph', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.golf_cart_max_persons', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.golf_cart_max_mph', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.sailing_vessel_length_ft',
  'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.inboard_hp', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.outboard_hp', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.newly_acquired_report_days',
  'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_length_ft', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_engine_hp', 'field'),
 ('homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_rental_max_days',
  'field'),
 ('homeowners.section_ii_liability_coverages.coverage_f_medical_payments_per_occurrence_premium', 'field'),
 ('homeowners.section_ii_liability_coverages.residence_employee_hours_threshold', 'field'),
 ('homeowners.section_ii_liability_coverages.damage_to_property_of_others_statement_days', 'field'),
 ('homeowners.deductibles.all_other_perils_deductible_type', 'field'),
 ('homeowners.deductibles.named_storm_deductible_percentage', 'field'),
 ('homeowners.deductibles.water_backup_deductible', 'field'),
 ('homeowners.deductibles.deductible_waiver_threshold', 'field'),
 ('homeowners.deductibles.named_storm_period_end_hours', 'field'),
 ('homeowners.rating_characteristics.policy_tier', 'field'),
 ('homeowners.rating_characteristics.premium_group', 'field'),
 ('homeowners.rating_characteristics.vandalism_malicious_mischief_option', 'field'),
 ('homeowners.scheduled_personal_property[].serial_number', 'field'),
 ('homeowners.scheduled_personal_property[].class_total_amount', 'field'),
 ('homeowners.scheduled_personal_property[].in_vault', 'field'),
 ('homeowners.scheduled_personal_property[].form_reference', 'field'),
 ('homeowners.scheduled_personal_property[].form_total_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].limit_percentage', 'field'),
 ('homeowners.optional_endorsement_coverages[].limit_percentage_basis', 'field'),
 ('homeowners.optional_endorsement_coverages[].minimum_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].maximum_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].limit_increase_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].off_premises_limit_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions', 'list_obj'),
 ('homeowners.optional_endorsement_coverages[].extensions[].name', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].limit_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].deductible_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].notes', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].parent_name', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].limit_percentage', 'field'),
 ('homeowners.optional_endorsement_coverages[].extensions[].limit_percentage_basis', 'field'),
 ('homeowners.optional_endorsement_coverages[].applies_to_locations', 'list_scalar'),
 ('homeowners.optional_endorsement_coverages[].per_day_limit_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].total_payment_cap_amount', 'field'),
 ('homeowners.optional_endorsement_coverages[].consequential_loss_radius_feet', 'field'),
 ('homeowners.optional_endorsement_coverages[].notice_days', 'field'),
 ('homeowners.discounts[].reason', 'field'),
 ('homeowners.discounts[].location_reference', 'field'),
 ('homeowners.mortgagees[].status', 'field'),
 ('homeowners.mortgagees[].cancellation_notice_days', 'field'),
 ('homeowners.mortgagees[].location_reference', 'field'),
 ('homeowners.mortgagees[].proof_of_loss_days', 'field'),
 ('homeowners.special_limits_of_liability[].limit_group', 'field'),
 ('homeowners.scheduled_other_structures[].square_footage', 'field'),
 ('homeowners.scheduled_other_structures[].year_built', 'field'),
 ('homeowners.scheduled_other_structures[].construction_type', 'field'),
 ('homeowners.scheduled_other_structures[].total_value', 'field'),
 ('homeowners.scheduled_other_structures[].has_structures_description', 'field'),
 ('homeowners.scheduled_locations[].address.municipality', 'field'),
 ('homeowners.scheduled_locations[].address.sub_county', 'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_a_dwelling_premium', 'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_b_other_structures_premium',
  'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_c_personal_property_premium',
  'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_d_loss_of_use_premium', 'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_a_coverage_tier', 'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.coverage_c_coverage_tier', 'field'),
 ('homeowners.scheduled_locations[].section_i_property_coverages.personal_property_loss_settlement_basis',
  'field'),
 ('homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_f_medical_payments_per_person_limit',
  'field'),
 ('homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_f_medical_payments_per_occurrence_limit',
  'field'),
 ('homeowners.scheduled_locations[].deductibles.deductible_waiver_threshold', 'field'),
 ('homeowners.scheduled_locations[].deductibles.water_backup_deductible', 'field'),
 ('homeowners.scheduled_locations[].applicable_forms[].limit_amount', 'field'),
 ('homeowners.scheduled_locations[].acreage', 'field'),
 ('homeowners.scheduled_locations[].causes_of_loss_form', 'field'),
 ('homeowners.scheduled_locations[].deductible_type', 'field'),
 ('homeowners.scheduled_locations[].solid_fuel_burning_device_present', 'field'),
 ('homeowners.scheduled_locations[].swimming_pool', 'field'),
 ('homeowners.scheduled_locations[].property_premium', 'field'),
 ('homeowners.scheduled_locations[].inland_marine_premium', 'field'),
 ('homeowners.scheduled_locations[].discounts', 'list_obj'),
 ('homeowners.scheduled_locations[].discounts[].discount_name', 'field'),
 ('homeowners.scheduled_locations[].discounts[].discount_type', 'field'),
 ('homeowners.scheduled_locations[].discounts[].amount', 'field'),
 ('homeowners.scheduled_locations[].policy_form_number', 'field'),
 ('homeowners.scheduled_locations[].program_name', 'field'),
 ('homeowners.scheduled_locations[].related_policy_number', 'field'),
 ('homeowners.scheduled_locations[].townhouse_rowhouse_indicator', 'field'),
 ('homeowners.scheduled_locations[].doublewide_indicator', 'field'),
 ('homeowners.scheduled_locations[].number_of_units', 'field'),
 ('homeowners.scheduled_locations[].units_between_fire_walls', 'field'),
 ('homeowners.scheduled_locations[].lead_abatement', 'field'),
 ('homeowners.scheduled_locations[].certificate_of_occupancy_date', 'field'),
 ('homeowners.scheduled_locations[].months_occupied_annually', 'field'),
 ('homeowners.scheduled_locations[].roof_updated_within_20_years', 'field'),
 ('homeowners.scheduled_locations[].roof_year_installed', 'field'),
 ('homeowners.scheduled_locations[].heating_type', 'field'),
 ('homeowners.scheduled_locations[].heating_installation_year', 'field'),
 ('homeowners.scheduled_locations[].secondary_heating_type', 'field'),
 ('homeowners.scheduled_locations[].basement_type', 'field'),
 ('homeowners.scheduled_locations[].fuel_tank_location', 'field'),
 ('homeowners.scheduled_locations[].gated_community', 'field'),
 ('homeowners.scheduled_locations[].renovation', 'object'),
 ('homeowners.scheduled_locations[].renovation.heating_year', 'field'),
 ('homeowners.scheduled_locations[].renovation.roof_year', 'field'),
 ('homeowners.scheduled_locations[].renovation.plumbing_year', 'field'),
 ('homeowners.scheduled_locations[].renovation.electrical_year', 'field'),
 ('homeowners.scheduled_locations[].renovation.heating_updated', 'field'),
 ('homeowners.scheduled_locations[].renovation.roof_updated', 'field'),
 ('homeowners.scheduled_locations[].renovation.plumbing_updated', 'field'),
 ('homeowners.scheduled_locations[].renovation.electrical_updated', 'field'),
 ('homeowners.scheduled_locations[].premium_group', 'field'),
 ('homeowners.scheduled_locations[].roof_to_wall_attachment', 'field'),
 ('homeowners.scheduled_locations[].opening_protection', 'field'),
 ('homeowners.scheduled_locations[].roof_shape', 'field'),
 ('homeowners.scheduled_personal_property_total', 'field'),
 ('homeowners.valuable_articles_classes', 'list_obj'),
 ('homeowners.valuable_articles_classes[].class_description', 'field'),
 ('homeowners.valuable_articles_classes[].blanket_amount', 'field'),
 ('homeowners.valuable_articles_classes[].blanket_per_item_limit', 'field'),
 ('homeowners.valuable_articles_classes[].itemized_amount', 'field'),
 ('homeowners.valuable_articles_classes[].deductible_amount', 'field'),
 ('homeowners.valuable_articles_classes[].premium', 'field'),
 ('homeowners.valuable_articles_classes[].market_value_cap_percentage', 'field'),
 ('homeowners.roof_surfacing_loss_schedule', 'list_obj'),
 ('homeowners.roof_surfacing_loss_schedule[].roof_age_years', 'field'),
 ('homeowners.roof_surfacing_loss_schedule[].roof_material', 'field'),
 ('homeowners.roof_surfacing_loss_schedule[].payment_percentage', 'field'),
 ('homeowners.seasonal_rental', 'list_obj'),
 ('homeowners.seasonal_rental[].applies_to', 'field'),
 ('homeowners.seasonal_rental[].location_reference', 'field'),
 ('homeowners.seasonal_rental[].number_of_weeks_rented', 'field'),
 ('homeowners.seasonal_rental[].waterfront_property', 'field'),
 ('homeowners.seasonal_rental[].watercraft_offered_with_rental', 'field'),
 ('homeowners.seasonal_rental[].recreational_vehicles_offered_with_rental', 'field'),
 ('homeowners.seasonal_rental[].trampoline_on_premises', 'field'),
 ('homeowners.seasonal_rental[].surcharge_amount', 'field'),
 ('homeowners.value_added_services', 'list_obj'),
 ('homeowners.value_added_services[].service_name', 'field'),
 ('homeowners.value_added_services[].provider', 'field'),
 ('homeowners.value_added_services[].phone', 'field'),
 ('homeowners.value_added_services[].website', 'field'),
 ('homeowners.value_added_services[].form_reference', 'field'),
 ('homeowners.value_added_services[].service_description', 'field'),
 ('homeowners.value_added_services[].eligibility', 'field'),
 ('homeowners.valuable_articles_extra_coverages', 'list_obj'),
 ('homeowners.valuable_articles_extra_coverages[].coverage_name', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].limit_percentage', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].limit_percentage_basis', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].limit_amount', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].maximum_amount', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].reporting_days', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].notes', 'field'),
 ('homeowners.valuable_articles_extra_coverages[].loan_period_days', 'field'),
 ('homeowners.form_provisions', 'list_obj'),
 ('homeowners.form_provisions[].form_reference', 'field'),
 ('homeowners.form_provisions[].provision_name', 'field'),
 ('homeowners.form_provisions[].value', 'field'),
 ('homeowners.form_provisions[].unit', 'field'),
 ('homeowners.form_provisions[].applies_to', 'field'),
 ('homeowners.form_provisions[].notes', 'field'),
 ('underwriting', 'object'),
 ('underwriting.prior_insurance', 'object'),
 ('underwriting.prior_insurance.carrier_name', 'field'),
 ('underwriting.prior_insurance.policy_number', 'field'),
 ('underwriting.prior_insurance.expiration_date', 'field'),
 ('underwriting.prior_insurance.notes', 'field'),
 ('underwriting.prior_cancellation_or_refusal', 'field'),
 ('underwriting.other_policies_with_carrier', 'field'),
 ('underwriting.prior_underwriting_approval', 'field'),
 ('underwriting.agency_visual_inspection', 'field'),
 ('underwriting.overall_risk_condition', 'field'),
 ('underwriting.has_commercial_policy_for_business', 'field'),
 ('underwriting.application_questions', 'list_obj'),
 ('underwriting.application_questions[].section', 'field'),
 ('underwriting.application_questions[].question', 'field'),
 ('underwriting.application_questions[].answer', 'field'),
 ('underwriting.application_questions[].explanation', 'field'),
 ('underwriting.insurance_scores', 'list_obj'),
 ('underwriting.insurance_scores[].insured_name', 'field'),
 ('underwriting.insurance_scores[].ordered_date', 'field'),
 ('underwriting.insurance_scores[].report_vendor', 'field'),
 ('underwriting.insurance_scores[].coded_score', 'field'),
 ('underwriting.exceptions', 'list_obj'),
 ('underwriting.exceptions[].level', 'field'),
 ('underwriting.exceptions[].exception_type', 'field'),
 ('underwriting.exceptions[].original_value', 'field'),
 ('underwriting.exceptions[].overridden_value', 'field'),
 ('underwriting.consumer_report_disclosures', 'list_obj'),
 ('underwriting.consumer_report_disclosures[].notice_type', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency', 'field'),
 ('underwriting.consumer_report_disclosures[].report_types', 'list_scalar'),
 ('underwriting.consumer_report_disclosures[].reference_number', 'field'),
 ('underwriting.consumer_report_disclosures[].adverse_action_factors', 'list_scalar'),
 ('underwriting.consumer_report_disclosures[].dispute_contact_phone', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address', 'object'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.line_1', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.line_2', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.city', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.state', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.postal_code', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.county', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.country', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_address.county_code', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_website', 'field'),
 ('underwriting.consumer_report_disclosures[].free_report_request_days', 'field'),
 ('underwriting.consumer_report_disclosures[].reevaluation_days', 'field'),
 ('underwriting.consumer_report_disclosures[].updated_report_days', 'field'),
 ('underwriting.consumer_report_disclosures[].form_reference', 'field'),
 ('underwriting.consumer_report_disclosures[].reporting_agency_phone', 'field'),
 ('underwriting.prior_losses_last_5_years', 'field')]

# ── 2. merged duplicates (removed field -> kept field) ──────────────────────
MERGES = {
    "homeowners.dwelling.distance_to_fire_station": "homeowners.rating_characteristics.distance_to_fire_station",
    "homeowners.dwelling.distance_to_hydrant": "homeowners.rating_characteristics.feet_from_hydrant",
    "homeowners.dwelling.vacancy_threshold_days": "homeowners.dwelling.vacancy_thresholds[].days",
    "homeowners.dwelling.number_of_weeks_rented": "homeowners.seasonal_rental[].number_of_weeks_rented",
    "homeowners.scheduled_locations[].number_of_weeks_rented": "homeowners.seasonal_rental[].number_of_weeks_rented",
}

# ── 3. printed labels ───────────────────────────────────────────────────────
ALIASES = {'document.document_title_as_stated': ['Evidence of Insurance'],
 'document.coverage_parts_present': ['Homes and Contents'],
 'document.applicable_coverages': [],
 'document.transaction_type': ['Amended Declaration',
                               'CHANGE ENDORSEMENT',
                               'ENDORSED POLICY',
                               'Renewal',
                               'Renewal Of',
                               'TRANS TYPE',
                               'Transaction',
                               'Transaction Type'],
 'document.transaction_reason': ['POLICY CHANGE',
                                 'Policy Change',
                                 'Reason(s) for Modification',
                                 'The Reason(s) For This Change Are As Follows',
                                 'Transaction Reason'],
 'document.transaction_effective_date': ['Amended',
                                         'Amended Date',
                                         'Amended Declarations Page as of',
                                         'As of',
                                         'EFF DATE',
                                         'Effective Date of Change',
                                         'ENDORSED POLICY EFF',
                                         'Policy Changes Effective',
                                         'Transaction Effective',
                                         'TRANSACTION EFFECTIVE DATE',
                                         'Transaction Effective Date'],
 'document.issue_date': ['Issue Date', 'Issued On Date', 'TRANSACTION DATE'],
 'document.print_date': ['Date Printed',
                         'Date Summary Printed',
                         'Last Updated',
                         'Online Policy Summary as of',
                         'Print Date',
                         'Printed On',
                         'Process Date',
                         'PROCESSING DATE'],
 'document.page_count': ['OF', 'Page n of N'],
 'document.source_system': ['Please see the Forms tab in'],
 'document.copy_type': ['Agent Copy',
                        'Company Copy',
                        'File Copy',
                        'Insured Copy',
                        'Insured Image',
                        'Office Copy',
                        'Reference Copy'],
 'document.summary_of_changes': ['Changes',
                                 'ENDORSEMENTS SUMMARY',
                                 'Summary of Changes',
                                 'Summary of Your Changes'],
 'document.document_form_number': ['Form No.', 'Form no.'],
 'document.transaction_expiration_date': ['Transaction Expiration'],
 'document.term_sequence': ['Term-Seq'],
 'document.mailed_date': ['Date Mailed'],
 'document.remarks': ['REMARKS', 'Remarks'],
 'document.total_locations': ['Coverage Information for Location', 'Property'],
 'document.mail_to': ['Mail To'],
 'document.changes': ['Changes made to your policy are as follows',
                      'It is hereby agreed and understood that the following change was made to your policy'],
 'document.changes[].effective_date': ['Changes made'],
 'document.changes[].location_reference': ['Location'],
 'document.changes[].old_value': ['Changed from'],
 'document.changes[].new_value': ['Added', 'to'],
 'document.changes[].detail_on_declarations_indicator': ['* - See Declarations for Detail'],
 'document.package_index': ['Contents', 'INDEX', 'Table of Contents'],
 'document.package_index[].form_number': ['Form no'],
 'document.package_index[].edition_date': ['Edition Date'],
 'document.package_index[].form_title': ['Chapter'],
 'document.package_index[].index_section': ['ENDORSEMENTS', 'FOR YOUR INFORMATION'],
 'document.package_index[].page_reference': ['Page', 'Starting On Page'],
 'document.package_index[].state': ['State'],
 'document.esignature_certificate': ['Document Completion Certificate'],
 'document.esignature_certificate.document_reference': ['Document Reference'],
 'document.esignature_certificate.document_title': ['Document Title'],
 'document.esignature_certificate.document_region': ['Document Region'],
 'document.esignature_certificate.sender_name': ['Sender Name'],
 'document.esignature_certificate.sender_email': ['Sender Email'],
 'document.esignature_certificate.total_pages': ['Total Document Pages'],
 'document.esignature_certificate.secondary_security': ['Secondary Security'],
 'document.esignature_certificate.participants': ['Participants'],
 'document.esignature_certificate.history': ['Document History'],
 'document.esignature_certificate.history[].timestamp': ['Timestamp'],
 'document.esignature_certificate.history[].event_description': ['Description'],
 'document.esignature_certificate.attached_page_count': ['page(s) attached here'],
 'document.not_a_bill_indicator': ['THIS IS NOT A BILL'],
 'document.enclosures_requiring_action': ['Please review these documents',
                                          'Please review, complete, and mail the following forms'],
 'document.page_number': ['PAGE', 'Page'],
 'carrier.company_name': ['Company Name'],
 'carrier.writing_company_name': ['Insurance Provided By',
                                  'Issued by',
                                  'Underwriting Company',
                                  'Your Insurer'],
 'carrier.group_name': ['a subsidiary or affiliate of'],
 'carrier.naic_number': ['NAIC'],
 'carrier.address': ['Home Office'],
 'carrier.contact.phone': ['Home', 'Mobile', 'Phone', 'Work'],
 'carrier.contact.fax': ['Fax'],
 'carrier.surplus_lines_broker_name': ['Surplus Lines Producer Name and Address'],
 'carrier.surplus_lines_license_number': ['Surplus Lines Producer License Number'],
 'carrier.company_structure': ['(A Stock Company)',
                               'A Mutual Company',
                               'A New York State Advance Premium Co-Operative Fire Insurance Corporation',
                               'A Reciprocal',
                               'A Stock Company',
                               'A Stock Corporation',
                               'Assessment Cooperative Fire Insurance Company',
                               'Mutual Company',
                               'Stock Company'],
 'carrier.state_of_incorporation': ['a stock company incorporated in'],
 'carrier.surplus_lines_broker_address': ['Surplus Lines Producer Name and Address'],
 'carrier.surplus_lines_filing': ['Excess Line Association of New York'],
 'carrier.surplus_lines_filing.document_id': ['Id'],
 'carrier.program_administrator.address': ['write MSI at'],
 'carrier.additional_contacts': ['Client Portal',
                                 'Consumer Reports Unit',
                                 'Customer Care Team',
                                 'Customer Portal',
                                 'For Policy Service',
                                 'Producer Compensation',
                                 'Questions?'],
 'carrier.additional_contacts[].phone': ['or call', 'Telephone'],
 'carrier.additional_contacts[].email': ['email'],
 'carrier.additional_contacts[].department': ['Attention', 'Attention: Privacy Inquiries'],
 'carrier.additional_contacts[].address': ['If you would like to contact us, please write to us at',
                                           'Mail to'],
 'carrier.fiscal_year_period': ['fiscal year'],
 'carrier.annual_meeting_schedule': ['annual meeting', 'Annual Meetings'],
 'carrier.bylaws': ['BY-LAWS', 'By-Laws'],
 'carrier.bylaws.board_size_min': ['Number and Qualifications'],
 'carrier.bylaws.board_size_max': ['Number and Qualifications'],
 'carrier.bylaws.director_term_years': ['Election'],
 'carrier.bylaws.nomination_notice_days': ['Nomination'],
 'carrier.bylaws.quorum': ['Quorum and Vote'],
 'carrier.bylaws.special_meeting_notice_days': ['Special Meetings'],
 'carrier.bylaws.board_meeting_notice_days': ['Meetings'],
 'carrier.bylaws.min_additional_board_meetings': ['Meetings'],
 'carrier.bylaws.board_meeting_call_min_directors': ['Meetings'],
 'carrier.bylaws.executive_committee_min_size': ['Executive Committee', 'Number and Power'],
 'carrier.bylaws.executive_committee_term_years': ['Executive Committee'],
 'carrier.bylaws.officer_term_years': ['Officers'],
 'carrier.bylaws.removal_vote_fraction': ['Removal and Vacancies'],
 'carrier.bylaws.additional_nominee_min_members': ['Nomination'],
 'carrier.bylaws.indemnification_notice_days': ['Authority'],
 'carrier.bylaws.amendment_submission_days': ['Amendments'],
 'producer': ['Agency',
              'Agency Address',
              'Agency Information',
              'AGENCY NAME AND ADDRESS',
              'Agent',
              'Broker',
              'Producer',
              "Your Agency's Name and Address",
              'Your Agency’s Name and Address'],
 'producer.agency_name': ['Agency', 'Broker/Agent Name and Address', 'Name', 'Producer name'],
 'producer.producer_code': ['Agency Code', 'Agency Information #', 'Agent', 'Code', 'PIB'],
 'producer.producer_contact_name': ['Agency Service Representative', 'Name'],
 'producer.address': ['Broker/Agent Name and Address', 'Name and Mailing Address'],
 'producer.contact.phone': ['Agent Phone',
                            'Home',
                            'Mobile',
                            'O',
                            'Office',
                            'Phone',
                            'Phone Number',
                            'PHONE O',
                            'Work'],
 'producer.contact.fax': ['Agent Fax', 'F', 'Fax'],
 'producer.contact.email': ['EMAIL', 'Email'],
 'producer.contact.website': ['Website'],
 'producer.commission_percentage': ['POL COMM'],
 'producer.producer_sub_code': ['PRODUCER SUB-CODE'],
 'producer.territory': ['TERRITORY', 'Territory'],
 'producer.paperless_indicator': ['Paper Off'],
 'producer.direct_mail_indicator': ['Direct Mail'],
 'producer.producer_contact_phone': ['Phone'],
 'producer.producer_contact_email': ['Email Address'],
 'policy': ['Policy Details', 'POLICY INFORMATION', 'Policy Information'],
 'policy.policy_number': ['POLICY',
                          'Policy #',
                          'Policy ID',
                          'Policy no.',
                          'Policy Number',
                          'Your Policy Number'],
 'policy.account_id': ['Account ID', 'BILLING ACCOUNT #', 'Your Account Number'],
 'policy.alternate_policy_identifiers': ['CONTRACT #', 'DOWNLOAD TRACKING #', 'File #', 'QUOTE #'],
 'policy.program_name': ['Coverage Level', 'SPECIAL PROGRAM'],
 'policy.policy_form_number': ['BASIC FORM',
                               'Basic Form',
                               'Cause of Loss Form',
                               'Causes of Loss Form',
                               'Form',
                               'Policy Form'],
 'policy.policy_type': ['Policy Type', 'Type'],
 'policy.effective_date': ['Both dates',
                           'Effective Date',
                           'Effective Date Of Policy',
                           'Policy Effective',
                           'Policy Effective Date',
                           'Policy period',
                           'Policy Period From',
                           'Policy Term',
                           'Policy Term Effective Date',
                           'Start Date'],
 'policy.expiration_date': ['Expiration Date',
                            'Expiry Date',
                            'Policy Expiration',
                            'Policy Expiration Date',
                            'Policy Period',
                            'Policy Period To',
                            'Policy Term',
                            'Policy Term Expiration Date',
                            'to'],
 'policy.effective_time': ['Policy Effective Date', 'Policy period'],
 'policy.time_zone': ['Policy period'],
 'policy.policy_term_months': ['Term Length'],
 'policy.minimum_earned_premium_percentage': ['minimum earned premium'],
 'policy.plan_type': ['Co-operative Plan',
                      'Cooperative Plan',
                      'Non-Participating',
                      'Participating',
                      'Policy Issued on the Co-Operative Plan',
                      'THIS NON-ASSESSABLE POLICY IS ISSUED ON THE CO-OPERATIVE PLAN',
                      'THIS POLICY IS ISSUED BY A CO-OPERATIVE INSURER',
                      'THIS POLICY IS ISSUED ON THE CO-OPERATIVE ASSESSMENT PLAN'],
 'policy.is_assessable': ['Assessable',
                          'Non- Assessable Policy',
                          'Non-Assessable',
                          'Non-Assessable Policy',
                          'THIS NON-ASSESSABLE POLICY IS ISSUED ON THE CO-OPERATIVE PLAN'],
 'policy.expiration_time': ['Expiration Time', 'Policy Expiration Date'],
 'policy.policyholder_since_date': ['Continuously Insured Since',
                                    'Customer Since',
                                    'Insured Since',
                                    'Policyholder Since',
                                    'Protected Since Date'],
 'policy.original_inception_date': ['INCEPTION DATE', 'Inception Date'],
 'policy.is_continuous_renewal': ['CONTINUOUS RENEWAL PLAN'],
 'policy.minimum_earned_premium_amount': ['minimum earned premium'],
 'policy.minimum_refund_amount': ['Any unearned premium amounts under'],
 'policy.service_of_suit_designee': ['Service of Suit'],
 'policy.required_policy_period_years': ['Required Policy Period'],
 'policy.suit_limitation_period': ['Legal action against us', 'Suit Against Us'],
 'policy.cancellation_notice_terms': ['Cancellation',
                                      'D. Nonrenewal',
                                      'Nonrenewal',
                                      'Our cancellation',
                                      'Your cancellation'],
 'policy.cancellation_notice_terms[].reason': ['All Other Situations',
                                               'New Policy',
                                               'Non-Payment of Premium',
                                               'Non-Renewal',
                                               'Policy with Term over One Year'],
 'policy.assessment_contingent_liability_multiple': ['contingent liability'],
 'policy.assessment_penalty_percentage': ['Action to Collect'],
 'policy.liberalization_period_days': ['Liberalization', 'Liberalization Clause'],
 'policy.assessment_notice_days': ['ASSESSMENTS', 'Notice'],
 'policy.assessment_payment_period_min_days': ['ASSESSMENTS'],
 'policy.assessment_payment_period_max_days': ['ASSESSMENTS'],
 'policy.assessment_collection_days': ['Collection'],
 'policy.new_policy_period_days': ['C. Cancellation', 'New Policy', 'Within 60 days'],
 'policy.cancellation_refund_method': ['Refund'],
 'named_insured.primary_name': ['APPLICANT NAME AND ADDRESS',
                                'Insured Name',
                                'Insured Name and Mailing Address',
                                "Insured's Name",
                                'Name',
                                'Name and address',
                                'Name and address of Insured',
                                'Name and Mailing Address',
                                'Named Insured',
                                'Named Insured & Mailing Address',
                                'Named Insured and Address',
                                'Named Insured and Mailing Address',
                                'Named Insured(s)',
                                'Named Insured(s) & Property Address',
                                "Senior Citizen Insured's Name",
                                "Senior Citizen Insured's Name: & Mailing Address"],
 'named_insured.mailing_address': ['Address',
                                   'ATTN',
                                   'Attn',
                                   'Insured Name and Mailing Address',
                                   'Mailing Address',
                                   'Named Insured and Mailing Address'],
 'named_insured.contact.email': ['EMAIL', 'Email'],
 'named_insured.contact.phones': ['Contact Info', 'PHONE', 'Primary Phone', 'Secondary Phone'],
 'named_insured.contact.phones[].phone_type': ['C', 'H', 'Type', 'W'],
 'named_insured.contact.phones[].number': ['Information'],
 'named_insured.contact.phones[].contact_name': ['Contact Name'],
 'named_insured.name_as_printed': ['NAME PRINTED ON DEC PAGES'],
 'named_insured.delivery_preference': ['Delivery Preference',
                                       'Insured paperless dec',
                                       'Insured paperless invoice'],
 'named_insured.individuals': ['EMPLOYMENT INFORMATION',
                               'INSURED INFORMATION',
                               'Insured Information',
                               'Insured Summary'],
 'named_insured.individuals[].name': ['Insured Name', 'NAME'],
 'named_insured.individuals[].insured_type': ['TYPE'],
 'named_insured.individuals[].role': ['ROLE APPENDAGE'],
 'named_insured.individuals[].date_of_birth': ['Date of Birth', 'DOB'],
 'named_insured.individuals[].marital_status': ['MAR', 'Marital Status'],
 'named_insured.individuals[].gender': ['Gender', 'SEX'],
 'named_insured.individuals[].ssn_masked': ['SSN'],
 'named_insured.individuals[].occupation': ['Occupation', 'OCCUPATION NAME'],
 'named_insured.individuals[].employment_status': ['EMPLOYMENT STATUS'],
 'named_insured.individuals[].business_on_premises': ['BUSINESS ON PREMISES'],
 'named_insured.third_party_designee': ['CANCELLATION OR NON-RENEWAL NOTICES',
                                        'IMPORTANT NOTICE TO ALL INSUREDS, INCLUDING SENIOR CITIZENS',
                                        'IMPORTANT SENIOR CITIZEN INFORMATION',
                                        'Name and Address of Third Party Designee',
                                        'NOTICE TO SENIOR CITIZEN INSUREDS',
                                        'Request To Designate a Third Party for Receipt of Duplicate Policy '
                                        'Notices',
                                        'Request To Designate A Third Party To Receive A Copy Of Policy '
                                        'Termination or Conditional Renewal',
                                        'Third Party Designation',
                                        'THIRD PARTY DESIGNATION NOTIFICATION'],
 'named_insured.third_party_designee.name': ['Name',
                                             'Name of "Designee"',
                                             'Name of "Designee" (print)',
                                             'Third-Party Designee',
                                             'Third-Party Designee: & Mailing Address'],
 'named_insured.third_party_designee.address': ['Mailing Address',
                                                'Third-Party Designee Mailing Address',
                                                'Third-Party Designee: & Mailing Address'],
 'named_insured.third_party_designee.address.line_1': ['Address',
                                                       'Mailing Address',
                                                       'Street',
                                                       'Street (print)',
                                                       'Third-Party Designee: & Mailing Address'],
 'named_insured.third_party_designee.address.city': ['City', 'City (print)'],
 'named_insured.third_party_designee.address.state': ['State'],
 'named_insured.third_party_designee.address.postal_code': ['ZIP'],
 'named_insured.third_party_designee.email': ['Electronic Mail Address'],
 'named_insured.third_party_designee.policy_type': ['Check Policy Type'],
 'named_insured.third_party_designee.insured_signature_date': ['Date',
                                                               "Senior Citizen Insured's Signature",
                                                               'Signature',
                                                               'Signature of Insured',
                                                               'Signature of Senior Citizen Insured'],
 'named_insured.third_party_designee.designee_signature_date': ['Acceptance Signature of Third Party '
                                                                'Designee',
                                                                'Date',
                                                                'Signature of Third Party "Designee"',
                                                                'Signature of Third Party Designee',
                                                                'Third-Party Designee'],
 'named_insured.third_party_designee.eligibility_age': ['age 65 or older', 'If you are age 65 or older'],
 'named_insured.third_party_designee.designation_effective_business_days': ['will become effective no later '
                                                                            'than'],
 'named_insured.third_party_designee.return_instructions': ['Mail to',
                                                            'Return Instructions',
                                                            'Returning it to'],
 'named_insured.third_party_designee.return_instructions.name': ['[Company] Name', 'Name'],
 'named_insured.third_party_designee.return_instructions.address.line_1': ['[Company] Address', 'Address'],
 'named_insured.third_party_designee.return_instructions.email': ['Electronic Mail Address', 'Email'],
 'named_insured.third_party_designee.return_instructions.fax': ['Fax'],
 'named_insured.third_party_designee.return_instructions.required_mail_method': ['certified mail, return '
                                                                                 'receipt requested'],
 'named_insured.third_party_designee.insured_date_of_birth': ['Date of Birth'],
 'named_insured.insured_definition_age_limits': ['"Insured"'],
 'named_insured.insured_definition_age_limits.student_theft_residence_days': ['9. Theft', 'Theft'],
 'named_insured.insured_definition_age_limits.max_roomers_boarders': ['"Business"',
                                                                      '"Incidental business property"',
                                                                      'Incidental Business Coverage'],
 'locations': ['Insured Property Location', 'Location of Business', 'Locationof Business', 'Locations'],
 'locations[].location_number': ['Location #'],
 'locations[].address.line_1': ['Address'],
 'locations[].address.sub_county': ['SUB COUNTY', 'Sub County'],
 'locations[].legal_description': ['Legal Description'],
 'interested_parties': ['Additional Insured',
                        'Additional Insured Information',
                        'ADDITIONAL INTEREST INFORMATION',
                        'ADDITIONAL INTEREST(S)',
                        'Additional Interests',
                        'Special Interests'],
 'interested_parties[].name': ['Name',
                               'Name and Address',
                               'Name and Address of Person or Organization',
                               'Name of Person or Organization'],
 'interested_parties[].address': ['Address of Person or Organization'],
 'interested_parties[].address.line_1': ['Address'],
 'interested_parties[].address.city': ['City, State, ZIP'],
 'interested_parties[].description_of_interest': ['Interest'],
 'interested_parties[].party_id': ['ID'],
 'interested_parties[].status': ['STATUS'],
 'interested_parties[].location_reference': ['Location of Premises'],
 'interested_parties[].applicable_coverages': ['Applicable Coverage(s)', 'Applies to'],
 'interested_parties[].other_coverages_specified': ['Other Coverage(s) As Specified'],
 'premium': ['Policy Premium', 'Premium Summary', 'Revised Annual Premium Summary', 'Total Premium'],
 'premium.total_policy_premium': ['Annual Policy Premium',
                                  'New Annual Premium',
                                  'Policy Total Premium',
                                  'Premium',
                                  'PREMIUM AT INCEPTION',
                                  'Premium At Inception',
                                  'Quoted Premium Amount',
                                  'Revised Annual Premium',
                                  'TERM AMOUNT',
                                  'Total',
                                  'Total Annual Policy Premium',
                                  'Total Policy Premium',
                                  'TOTAL PREMIUM',
                                  'Total Premium',
                                  'Total Premium for this Policy',
                                  'Total Quoted Premium',
                                  'Your premium was reduced to'],
 'premium.basic_premium': ['Base Premium before Deductible', 'Basic Coverage Premium', 'Basic Premium'],
 'premium.return_premium': ['Total return premium'],
 'premium.premium_by_coverage_part': ['Annual Premium Computation',
                                      'Annual Premium Computation and Applicable Policy Forms Requested',
                                      'Annual Premium Computation for Location #',
                                      'Coverage Details'],
 'premium.premium_by_coverage_part[].coverage_part': ['Coverage',
                                                      'Coverage / Form',
                                                      'DESCRIPTION',
                                                      'Homeowners',
                                                      'Homes and Contents'],
 'premium.premium_by_coverage_part[].premium': ['Premium'],
 'premium.premium_by_coverage_part[].applies_to': ['Coverage'],
 'premium.premium_by_coverage_part[].location_reference': ['Loc #/Bldg #'],
 'premium.premium_by_coverage_part[].property_covered': ['Property covered'],
 'premium.premium_by_coverage_part[].limit_amount': ['Amount', 'Limit', 'LIMIT AMOUNT'],
 'premium.premium_by_coverage_part[].deductible_amount': ['Deductible'],
 'premium.premium_by_coverage_part[].is_included': ['INCL.', 'Incl.', 'Included'],
 'premium.taxes_and_fees': ['Additional Charges'],
 'premium.surcharges': ['Surcharge Information'],
 'premium.surplus_lines_tax': ['Surplus Lines Tax'],
 'premium.stamping_fee': ['Stamping Fee'],
 'premium.inspection_fee': ['Inspection Fee'],
 'premium.forms_and_endorsements_premium': ['Endorsement Premium',
                                            'Forms/Endorsements Premium',
                                            'Optional Coverage Premium',
                                            'Total Endorsement Premium'],
 'premium.coverage_premium': ['Coverage Premium'],
 'premium.premium_before_discounts': ['Your insurance cost could have been'],
 'premium.total_discount_amount': ['annual premium savings of',
                                   'in discounts',
                                   'Savings Reflected in Your Total Premium',
                                   "That's a homeowner savings of",
                                   'Your homeowners premium was reduced by'],
 'premium.prior_annual_premium': ['Prior Annual Premium'],
 'premium.annual_premium_change': ['Annual Change in Premium', 'Change In Annual Premium'],
 'premium.pro_rata_premium_change': ['Amount',
                                     'NET CHANGE AMOUNT',
                                     'Premium adjustment for this change',
                                     'Pro-Rata Change in Premium',
                                     'Quoted Pro-rated Premium Amount'],
 'premium.premium_adjustment_method': ['Type'],
 'premium.broker_fee': ['Broker Fee'],
 'premium.number_of_risks': ['Total Number of Risks'],
 'premium.total_fees_amount': ['Fees'],
 'billing': ['ACCOUNT INFORMATION'],
 'billing.billing_plan': ['Billing Information'],
 'billing.payment_plan': ['Pay Plan', 'Policy Pay Plan', 'Your Policy Pay Plan is'],
 'billing.payment_method': ['ELECTRONIC FUND',
                            'Electronic Fund Transfer',
                            'Pay by Check',
                            'PAY TYPE',
                            'Repetitive EFT'],
 'billing.bill_to_party': ['Paid By'],
 'billing.amount_due': ['Remaining Balance', 'TOTAL DUE'],
 'billing.due_date': ['Please pay the total due upon receipt'],
 'billing.checks_payable_to': ['Make checks payable to', 'Please make all checks payable to'],
 'billing.remittance_address': ['mail the lower portion with your payment to',
                                'Please pay the total due upon receipt to'],
 'billing.invoice_date': ['Mortgage Invoice'],
 'billing.amount_enclosed': ['AMOUNT ENCLOSED'],
 'billing.bank_account_type': ['ACCOUNT TYPE'],
 'billing.bank_account_number_masked': ['ACCOUNT #'],
 'billing.preferred_due_day': ['PREFERRED DUE DAY'],
 'billing.payments': ['Billing Office Use',
                      'Payer Information',
                      'Payment Confirmation',
                      'Payment Details',
                      'Receipt of Payment'],
 'billing.payments[].payer_name': ['Name of Payer'],
 'billing.payments[].payer_address.line_1': ['Address'],
 'billing.payments[].payment_type': ['Payment Type'],
 'billing.payments[].account_number_masked': ['Account Number'],
 'billing.payments[].payment_status': ['Payment Status'],
 'billing.payments[].payment_date': ['Date Paid', 'Payment Date/Time', 'to initiate a payment on'],
 'billing.payments[].amount': ['Amount', 'AMOUNT PAID', 'for the amount of', 'Premium Amount'],
 'billing.payments[].period_start': ['Period'],
 'billing.payments[].insurer': ['I hereby authorize', 'Insurer'],
 'billing.payments[].account_holder_signature': ['Signature of Account Holder (Optional)'],
 'billing.fee_schedule': ['Fee Disclosure Endorsement'],
 'billing.fee_schedule[].fee_name': ['Installment Option Fee',
                                     'Notice of Cancellation for non payment of premium',
                                     'Returned Check Charge'],
 'forms_and_endorsements': ['attached at time of issue',
                            'Coverage Endorsements',
                            'Coverage Enhancements',
                            'Detailed Form Information',
                            'Forms and Endorsements',
                            'Forms/Endorsements',
                            'LOCATION FORMS',
                            'Optional Items',
                            'Policy Forms',
                            'Policy Forms & Optional Coverages',
                            'Policy Forms and Endorsements',
                            'Policy Subject to the Following Forms and Endorsements',
                            'Privacy Disclosure Notice',
                            'Required Forms and Endorsements Included in Your Policy',
                            'SCHEDULE OF ADDITIONAL ENDORSEMENTS',
                            'Service of Suit Endorsement',
                            'Subject to the Following Forms & Endorsements',
                            'Subject to the following forms and endorsements',
                            'Vehicle Under Construction Endorsement'],
 'forms_and_endorsements[].form_number': ['Form',
                                          'Form #',
                                          'FORM NAME',
                                          'Form No.',
                                          'Form no.',
                                          'Form Number',
                                          'NAME'],
 'forms_and_endorsements[].edition_date': ['Ed.',
                                           'EDITION',
                                           'Edition',
                                           'Edition Date',
                                           'FORM EDITION',
                                           'Rev.'],
 'forms_and_endorsements[].form_title': ['Description', 'Form Name', 'Title'],
 'forms_and_endorsements[].applies_to': ['For Location', 'LOC', 'Loc #/Bldg #'],
 'forms_and_endorsements[].limit_amount': ['COVERAGE LIMIT', 'Limit'],
 'forms_and_endorsements[].deductible_amount': ['Deductible', 'ITEM IV. DEDUCTIBLE'],
 'forms_and_endorsements[].premium': ['Cost', 'PREMIUM', 'Premium'],
 'forms_and_endorsements[].is_included': ['Incl', 'Incl.'],
 'forms_and_endorsements[].group_premium': ['Basic Forms'],
 'forms_and_endorsements[].state': ['State'],
 'forms_and_endorsements[].page_reference': ['Page'],
 'forms_and_endorsements[].details': ['DETAILS', 'FORM DETAILS'],
 'forms_and_endorsements[].applies_to_locations': ['Location'],
 'forms_and_endorsements[].copyright_notice': ['© Chubb.2016. All rights reserved', '© Copyright 1985 by'],
 'forms_and_endorsements[].statutory_reference': ['Insurance department requirement'],
 'loss_history': ['Loss History', 'MANUAL LOSSES'],
 'loss_history[].loss_date': ['DATE'],
 'loss_history[].description': ['DESCRIPTION'],
 'loss_history[].paid_amount': ['AMOUNT'],
 'loss_history[].category': ['CATEGORY'],
 'loss_history[].loss_source': ['LOSS FROM'],
 'loss_history[].points': ['POINTS'],
 'loss_history[].occurrence_count': ['OCCR'],
 'loss_history[].dispute_indicator': ['DISPUTE IND'],
 'loss_history[].catastrophe_indicator': ['CAT'],
 'state_notices[].notice_title': ['Earthquake Insurance Availability Notice for New Jersey',
                                  'Flood Insurance Notice for New Jersey',
                                  'FLOOD/MUDSLIDE EXCLUSION ADVISORY NOTICE TO POLICYHOLDERS - NEW YORK',
                                  'FLOOD/MUDSLIDE EXCLUSION ADVISORY NOTICE TO POLICYHOLDERS – NEW YORK',
                                  'Homeowners Insurance Summary for New Jersey',
                                  'IMPORTANT FLOOD INSURANCE NOTICE',
                                  'IMPORTANT NOTICE',
                                  'INSURANCE FRAUD WARNING NOTICE',
                                  'LVANIA NOTICE',
                                  'NEW YORK NOTICE',
                                  'NOTICE TO SENIOR CITIZENS',
                                  'PENNSYLVANIA NOTICE',
                                  'Policy Information Notice',
                                  'Privacy Disclosure Notice',
                                  'PRIVACY NOTICE',
                                  'State Notice',
                                  'U.S. PRIVACY NOTICE'],
 'state_notices[].form_reference': ['FORM'],
 'state_notices[].edition_date': ['Ed.', 'EDITION'],
 'state_notices[].contact_phone': ['by calling', 'The NFIP may be contacted by phone at'],
 'state_notices[].contact_website': ['via their website at', 'visit the website', 'visit the website below'],
 'state_notices[].affiliate_names': ['Companies Providing This Notice', 'Our affiliates include'],
 'state_notices[].regulator_contact': ['For Nevada residents only'],
 'state_notices[].privacy_sharing_practices[].reason': ['Reasons we can share your personal information'],
 'state_notices[].privacy_sharing_practices[].company_shares': ['Does Chubb share?', 'Does MSI share?'],
 'state_notices[].privacy_sharing_practices[].can_limit': ['Can you limit this sharing?'],
 'state_notices[].peril_summary': ['Your Policy Covers Losses Caused by',
                                   'Your Policy Does Not Cover Losses Caused by'],
 'state_notices[].loss_ratio_disclosure': ['for every $1.00 of earthquake insurance premium'],
 'state_notices[].provided_by': ['Who is providing this notice?'],
 'claim_reporting.claims_phone': ['Claim Service Center',
                                  'Claims Contact',
                                  'CUSTOMER CARE',
                                  'Customer Service',
                                  'For Claim Service',
                                  'If you need to report a claim',
                                  'Report a Claim',
                                  'To Report a Claim',
                                  'To report a claim please call'],
 'claim_reporting.proof_of_loss_days': ['Proof of loss',
                                        'submit an acceptable proof of loss',
                                        'submit to us a statement of loss'],
 'claim_reporting.claim_payment_days': ['J. Loss Payment', 'Loss Payment', 'Payment of Loss or Claim'],
 'claim_reporting.appraiser_selection_days': ['Appraisal', 'Appraisals'],
 'claim_reporting.umpire_selection_days': ['Appraisal', 'Appraisals'],
 'claim_reporting.repair_option_notice_days': ['Our Option', 'Our Options'],
 'claim_reporting.tax_lien_payment_days': ['certificate of lien', 'Liens for Unpaid Taxes'],
 'claim_reporting.estimate_provision_days': ['Estimation Of Claims'],
 'claim_reporting.judgment_payment_days': ['F. Suit Against Us'],
 'claim_reporting.declaratory_action_days': ['F. Suit Against Us', 'NY STATUTORY ENDORSEMENT'],
 'claim_reporting.suit_waiting_period_after_proof_days': ['Legal action against us'],
 'signature.authorized_representative_name': ['Authorized Company Representative',
                                              'Authorized Representative',
                                              'Authorized representative',
                                              'Our Authorized Representative'],
 'signature.title': [],
 'signature.signature_date': ['DATE'],
 'signature.officer_signatures': ['In Witness Whereof'],
 'signature.officer_signatures[].title': ['President',
                                          'Secretary',
                                          'Vice President',
                                          'Vice President /Secretary'],
 'signature.party_signatures': ['Applicant'],
 'signature.party_signatures[].role': ['Agent'],
 'signature.party_signatures[].signed_date': ['Date'],
 'signature.is_signed': ['SIGNATURE'],
 'homeowners.dwelling': ['Building Utilities',
                         'Information About Your Property',
                         'Location Details',
                         'Property Characteristics',
                         'TENANTS HOMEOWNERS UNDERWRITING (H04)'],
 'homeowners.dwelling.described_location': ['Address',
                                            'Described Location(s)',
                                            'Insured Location Information',
                                            'Insured Location of Residence Premises',
                                            'Insured Property Location',
                                            'Location',
                                            'Location Address Information',
                                            'Location(s) of Property Insured',
                                            'Named Insured(s) & Property Address',
                                            'Number, Street, Town or City, County, State, Zip Code',
                                            'PROPERTY LOCATION',
                                            'Residence Address',
                                            'Residence Premises'],
 'homeowners.dwelling.described_location.line_1': ['Street'],
 'homeowners.dwelling.described_location.city': ['City'],
 'homeowners.dwelling.described_location.state': ['State'],
 'homeowners.dwelling.described_location.postal_code': ['Zip'],
 'homeowners.dwelling.described_location.county': ['COUNTY', 'County', 'County Name'],
 'homeowners.dwelling.described_location.county_code': ['County Code'],
 'homeowners.dwelling.described_location.sub_county': ['SUB COUNTY', 'Sub County'],
 'homeowners.dwelling.occupancy_type': ['Occupancy', 'Occupancy Type'],
 'homeowners.dwelling.dwelling_type': ['Residence Type Code', 'Type of Home'],
 'homeowners.dwelling.construction_type': ['Construction', 'Construction Type'],
 'homeowners.dwelling.year_built': ['Construction Year', 'Year Built', 'Year of Construction'],
 'homeowners.dwelling.number_of_stories': ['# of Stories'],
 'homeowners.dwelling.square_footage': ['Square Footage'],
 'homeowners.dwelling.roof_type': ['Roof Material Type', 'Roof Type', 'Type Of Roof Surfacing Material'],
 'homeowners.dwelling.roof_age': ['Age of Roof'],
 'homeowners.dwelling.heating_type': ['PRIMARY HEAT SOURCE', 'Primary Heat Source', 'Primary Heating Type'],
 'homeowners.dwelling.protection_class': ['Fire Protection',
                                          'Fire Protection Class',
                                          'PROT CLASS',
                                          'Protection',
                                          'Protection Class',
                                          'Semi Protected',
                                          'Unprotected'],
 'homeowners.dwelling.territory_code': ['GL Territory', 'Rating Territory', 'TERR', 'Territory'],
 'homeowners.dwelling.market_value': ['Market Value'],
 'homeowners.dwelling.swimming_pool': ['Pool',
                                       'SWIMMING POOL',
                                       'Swimming Pool',
                                       'Swimming Pool, Dock or Beach'],
 'homeowners.dwelling.trampoline': ['Trampoline on Premises'],
 'homeowners.dwelling.dogs_on_premises': ['Are there any dogs owned',
                                          'Are there any dogs owned by the residents of the property?'],
 'homeowners.dwelling.alarm_type': ['What type of system?'],
 'homeowners.dwelling.basement_type': ['Basement',
                                       'Basement Construction',
                                       'FOUNDATION TYPE',
                                       'Foundation Type'],
 'homeowners.dwelling.basement_finished_percentage': ['Finished Basement'],
 'homeowners.dwelling.usage_type': ['Dwelling Use',
                                    'Is this primary residence of the insured?',
                                    'LOC TYPE',
                                    'Owner Occupied',
                                    'Primary Residence',
                                    'Risk Description',
                                    'Seasonal',
                                    'Seasonal/Secondary',
                                    'Secondary',
                                    'SECONDARY INDICATOR',
                                    'Usage'],
 'homeowners.dwelling.protective_devices': ['Protective Device'],
 'homeowners.dwelling.protective_devices[].device_type': ['Automatic (hard wired) Generator',
                                                          'Burglar Alarm',
                                                          'Central Fire & /or Burglar Alarm',
                                                          'Central Fire &/or Burglar Alarm',
                                                          'Central Station Alarm',
                                                          'Deadbolt',
                                                          'Deadbolts',
                                                          'Device',
                                                          'DISCOUNT DESCRIPTION',
                                                          'Fire Alarm',
                                                          'Fire Extinguisher',
                                                          'Fire Protective Device',
                                                          'Home Security Camera System with motion detection '
                                                          'and insured notification',
                                                          'Local Alarm',
                                                          'LOCAL FIRE ALARM',
                                                          'Premises Alarm',
                                                          'Professionally Monitored Fire Alarm',
                                                          'Protective Devices',
                                                          'Smoke Alarm',
                                                          'Smoke Detector',
                                                          'Smoke Detectors',
                                                          'Sprinklers',
                                                          'Water Leak Detection',
                                                          'Water Shutoff Device'],
 'homeowners.dwelling.protective_devices[].credit_percentage': ['PERCENTAGE'],
 'homeowners.dwelling.acreage': ['Acreage'],
 'homeowners.dwelling.legal_description': ['Legal Description'],
 'homeowners.dwelling.age_of_home': ['Age of Home'],
 'homeowners.dwelling.years_owned': ['How many years has the applicant owned this risk?'],
 'homeowners.dwelling.purchase_price': ['Purchase Price'],
 'homeowners.dwelling.cost_of_improvements': ['Cost of Improvements'],
 'homeowners.dwelling.roof_year_installed': ['ROOF INSTALLATION YEAR',
                                             'Year Of Installation',
                                             'Year Roof Updated'],
 'homeowners.dwelling.roof_updated_within_20_years': ['Has the roof been updated in the last 20 years?',
                                                      'ROOF RENOVATIONS'],
 'homeowners.dwelling.roof_shape': ['Hip Roof'],
 'homeowners.dwelling.roof_to_wall_attachment': ['Roof to Wall Attachment'],
 'homeowners.dwelling.opening_protection': ['Opening Protection'],
 'homeowners.dwelling.heating_fuel_type': ['Fuel Type'],
 'homeowners.dwelling.heating_installation_year': ['PRIMARY HEAT INSTALLATION YEAR'],
 'homeowners.dwelling.secondary_heating_type': ['ALTERNATE HEAT SOURCE', 'Secondary Heating Type'],
 'homeowners.dwelling.fuel_tank_location': ['FUEL TANK LOCATION'],
 'homeowners.dwelling.thermostat_controlled_central_heat': ['Thermostat Controlled Central Heat'],
 'homeowners.dwelling.electrical_service_type': ['Electrical Service'],
 'homeowners.dwelling.renovation.heating_year': ['Renov Heat'],
 'homeowners.dwelling.renovation.roof_year': ['Renov Roof'],
 'homeowners.dwelling.renovation.heating_updated': ['HEAT_YN'],
 'homeowners.dwelling.renovation.roof_updated': ['ROOF_YN'],
 'homeowners.dwelling.renovation.plumbing_updated': ['PLUMBING_YN'],
 'homeowners.dwelling.renovation.electrical_updated': ['ELECTRIC_YN'],
 'homeowners.dwelling.exterior_wall_type': ['Siding Type'],
 'homeowners.dwelling.number_of_bathrooms': ['# of Bathrooms'],
 'homeowners.dwelling.garage_type': ['Garage Type'],
 'homeowners.dwelling.garage_number_of_cars': ['Garage - Number of Cars', 'Garage Number of Cars'],
 'homeowners.dwelling.number_of_units': ['# of Apartments', 'Number of Apartments', 'NUMBER OF UNITS'],
 'homeowners.dwelling.units_between_fire_walls': ['# Units between Fire Walls', 'UNITS BETWEEN FIRE WALLS'],
 'homeowners.dwelling.townhouse_rowhouse_indicator': ['TOWN/ROW HOUSE', 'Town/Row House'],
 'homeowners.dwelling.doublewide_indicator': ['DOUBLEWIDE', 'Doublewide'],
 'homeowners.dwelling.lead_abatement': ['LEAD ABATEMENT', 'Lead Abatement'],
 'homeowners.dwelling.certificate_of_occupancy_date': ['CERTIFICATE OF OCCUPANCY DATE'],
 'homeowners.dwelling.gated_community': ['GATED COMMUNITY'],
 'homeowners.dwelling.visibility': ['Visibility'],
 'homeowners.dwelling.principal_unit_at_risk': ['Principal Unit-at-Risk'],
 'homeowners.dwelling.number_of_residence_employees': ['# of Employees'],
 'homeowners.dwelling.is_currently_occupied': ['Is this property currently occupied?'],
 'homeowners.dwelling.occupied_by_others': ['Is the dwelling occupied by anyone other than the named insured '
                                            'during the year?'],
 'homeowners.dwelling.is_rented_to_others': ['Will the dwelling be rented out at any time during the year?'],
 'homeowners.dwelling.months_occupied_annually': ['MONTHS OCCUPIED ANNUALLY'],
 'homeowners.dwelling.usage_explanation': ['If no, please explain'],
 'homeowners.dwelling.pipes_winterized': ['If home has indoor plumbing, are pipes winterized or drained?'],
 'homeowners.dwelling.accessible_year_round': ['Is the home accessible all year around?'],
 'homeowners.dwelling.caretaker.has_caretaker': ['Is there a caretaker or other person who checks on this '
                                                 'property when you are not there?'],
 'homeowners.dwelling.caretaker.name': ['Who?'],
 'homeowners.dwelling.waterfront_property': ['Waterfront Property'],
 'homeowners.dwelling.water_exposures': ['Any Water Exposures?'],
 'homeowners.dwelling.pool_features': ['Check any exposures that apply'],
 'homeowners.dwelling.dogs_count': ['How many?'],
 'homeowners.dwelling.dogs': ['Describe the breed of each dog on premises'],
 'homeowners.dwelling.dogs[].dog_number': ['Dog #'],
 'homeowners.dwelling.other_animals': ['Explain Other Animals', 'Type'],
 'homeowners.dwelling.business_on_premises': ['Any Business conducted on premises (in dwelling or '
                                              'outbuilding)?',
                                              'BUSINESS ON PREMISES'],
 'homeowners.dwelling.replacement_cost_estimator': ['ADJUSTED UNDER XACTWARE APPRAISAL SYSTEM'],
 'homeowners.dwelling.related_policy_number': ['PRIMARY POLICY NUMBER', 'Seasonal Policy Number'],
 'homeowners.dwelling.has_related_private_structures': ['Are there other structures on premises considered '
                                                        'to be related private structures?'],
 'homeowners.dwelling.business_on_premises_description': ['Describe'],
 'homeowners.dwelling.has_monitoring_system': ['Does dwelling have any type of monitoring system?'],
 'homeowners.dwelling.dogs_bite_history_any': ['Do any dogs have a history of biting?'],
 'homeowners.dwelling.dog_bite_history_explanation': ['Please explain history'],
 'homeowners.dwelling.secondary_heating_explanation': ['Explain Other'],
 'homeowners.dwelling.roof_type_explanation': ['Explain Other'],
 'homeowners.dwelling.slab_foundation': ['Slab'],
 'homeowners.dwelling.territory_sub_code': ['TERR'],
 'homeowners.dwelling.unoccupancy_threshold_days': ['"Unoccupied" means', 'Unoccupied'],
 'homeowners.dwelling.freeze_protection_min_temperature_f': ['Freezing water'],
 'homeowners.dwelling.vacancy_thresholds': ['vacant for more than'],
 'homeowners.dwelling.vacancy_thresholds[].days': ['vacant for more than'],
 'homeowners.dwelling.has_secondary_heating': ['Any Other Secondary Heating Source?'],
 'homeowners.dwelling.has_other_animals': ['Are there any other animals besides dogs?'],
 'homeowners.dwelling.building_description': ['Description'],
 'homeowners.section_i_property_coverages': ['Coverage Details',
                                             'Coverage Information',
                                             'Coverages and Limits of Liability',
                                             'Policy Coverage',
                                             'Policy Coverages',
                                             'Property Coverage Section',
                                             'Property Coverages',
                                             'Section I',
                                             'Section I - Property',
                                             'SECTION I - PROPERTY COVERAGES',
                                             'Section I Coverages',
                                             'SECTION I: PROPERTY DAMAGE'],
 'homeowners.section_i_property_coverages.coverage_a_dwelling_limit': ['A. Dwelling',
                                                                       'A. Residence',
                                                                       'A: DWELLING',
                                                                       'Cov A',
                                                                       'Cov A - Dwelling',
                                                                       'Cov A -- Dwelling',
                                                                       'Cov A – Dwelling',
                                                                       'Coverage A',
                                                                       'Coverage A - Dwelling',
                                                                       'Coverage A - Residence',
                                                                       'Coverage A -- Dwelling',
                                                                       'Coverage A -- Residence',
                                                                       'Coverage A DWELLING',
                                                                       'Coverage A Dwelling',
                                                                       'Coverage A – Dwelling',
                                                                       'Coverage A – Residence',
                                                                       'COVERAGE LIMIT',
                                                                       'Deluxe House Coverage',
                                                                       'DWELLING',
                                                                       'House',
                                                                       'Liability Limit',
                                                                       'LIMIT',
                                                                       'LIMIT AMOUNT',
                                                                       'Limit of Liability',
                                                                       'Limits',
                                                                       'Residence'],
 'homeowners.section_i_property_coverages.coverage_b_other_structures_limit': ['Appurtenant Structures',
                                                                               'B. Other Structures',
                                                                               'B. Private Structures',
                                                                               'B. Related Private '
                                                                               'Structures',
                                                                               'B: OTHER STRUCTURES',
                                                                               'Cov B',
                                                                               'Cov B - Other Structures',
                                                                               'Cov B -- Other Structures',
                                                                               'Cov B – Other Structures',
                                                                               'Coverage B',
                                                                               'Coverage B - Other '
                                                                               'Structures',
                                                                               'Coverage B - Related Private '
                                                                               'Structures',
                                                                               'Coverage B - Related Private '
                                                                               'Structures on the Premises',
                                                                               'Coverage B -- Other '
                                                                               'Structures',
                                                                               'Coverage B -- Related '
                                                                               'Private Structures',
                                                                               'Coverage B -- Related '
                                                                               'Private Structures on the '
                                                                               'Premises',
                                                                               'Coverage B OTHER STRUCTURES',
                                                                               'Coverage B – Other '
                                                                               'Structures',
                                                                               'Coverage B – Related Private '
                                                                               'Structures',
                                                                               'Coverage B – Related Private '
                                                                               'Structures on the Premises',
                                                                               'COVERAGE LIMIT',
                                                                               'Liability Limit',
                                                                               'LIMIT',
                                                                               'LIMIT AMOUNT',
                                                                               'Limit of Liability',
                                                                               'Limits',
                                                                               'Other permanent structures',
                                                                               'OTHER STRUCTURES',
                                                                               'Related Private Structures'],
 'homeowners.section_i_property_coverages.coverage_c_personal_property_limit': ['C. Personal Property',
                                                                                'C: PERSONAL PROPERTY',
                                                                                'Contents',
                                                                                'Cov C',
                                                                                'Cov C - Personal Property',
                                                                                'Cov C -- Personal Property',
                                                                                'Cov C – Personal Property',
                                                                                'Coverage C',
                                                                                'Coverage C - Personal '
                                                                                'Property',
                                                                                'Coverage C -- Personal '
                                                                                'Property',
                                                                                'Coverage C PERSONAL '
                                                                                'PROPERTY',
                                                                                'Coverage C – Personal '
                                                                                'Property',
                                                                                'COVERAGE LIMIT',
                                                                                'Deluxe Contents Coverage',
                                                                                'Deluxe or Standard Contents',
                                                                                'Liability Limit',
                                                                                'LIMIT',
                                                                                'LIMIT AMOUNT',
                                                                                'Limit of Liability',
                                                                                'Limits',
                                                                                'PERSONAL PROPERTY',
                                                                                'Personal Property',
                                                                                'Unscheduled Personal '
                                                                                'Property'],
 'homeowners.section_i_property_coverages.coverage_d_loss_of_use_limit': ["Add'l Living Exp. & Loss of Rent",
                                                                          'Additional Living Expense',
                                                                          'Additional living expenses',
                                                                          'Cov D',
                                                                          'Cov D - Addl Living Exp/Loss of '
                                                                          'Rents',
                                                                          'Cov D -- Addl Living Exp/Loss of '
                                                                          'Rents',
                                                                          'Cov D – Addl Living Exp/Loss of '
                                                                          'Rents',
                                                                          'Coverage D',
                                                                          'Coverage D - Additional Living '
                                                                          'Costs And Loss Of Rent',
                                                                          'Coverage D - Additional Living '
                                                                          'Expense and Loss of Rent',
                                                                          'Coverage D - Additional Living '
                                                                          'Expense or Loss of Rent',
                                                                          'Coverage D - Addl. Living Exp and '
                                                                          'Loss of Rent',
                                                                          'Coverage D - Loss of Use',
                                                                          'Coverage D -- Additional Living '
                                                                          'Costs And Loss Of Rent',
                                                                          'Coverage D -- Additional Living '
                                                                          'Expense and Loss of Rent',
                                                                          'Coverage D -- Additional Living '
                                                                          'Expense or Loss of Rent',
                                                                          'Coverage D -- Addl. Living Exp '
                                                                          'and Loss of Rent',
                                                                          'Coverage D -- Loss of Use',
                                                                          'Coverage D LOSS OF USE',
                                                                          'Coverage D – Additional Living '
                                                                          'Costs And Loss Of Rent',
                                                                          'Coverage D – Additional Living '
                                                                          'Expense and Loss of Rent',
                                                                          'Coverage D – Additional Living '
                                                                          'Expense or Loss of Rent',
                                                                          'Coverage D – Addl. Living Exp and '
                                                                          'Loss of Rent',
                                                                          'Coverage D – Loss of Use',
                                                                          'COVERAGE LIMIT',
                                                                          "D. Add'l Living Exp. & Loss of "
                                                                          'Rent',
                                                                          'D. Additional Living Expenses',
                                                                          'D. Living Exp. & Loss of Rent',
                                                                          'D. Loss Of Use',
                                                                          'D: LOSS OF USE',
                                                                          'Liability Limit',
                                                                          'LIMIT',
                                                                          'LIMIT AMOUNT',
                                                                          'Limit of Liability',
                                                                          'Limits',
                                                                          'Loss of Rents',
                                                                          'LOSS OF USE',
                                                                          'Loss Of Use (Cov. D)'],
 'homeowners.section_i_property_coverages.extended_replacement_cost_percentage': ['Additional Amount Of '
                                                                                  'Insurance',
                                                                                  'Additional Replacement '
                                                                                  'Cost'],
 'homeowners.section_i_property_coverages.ordinance_or_law_percentage': ['Ordinance or Law',
                                                                         'Ordinance or Law (25% of Coverage '
                                                                         'A - Dwelling Limit)',
                                                                         'Rebuilding to code'],
 'homeowners.section_i_property_coverages.loss_settlement_basis': ['ACTUAL CASH VALUE',
                                                                   'Actual Cash Value Provision',
                                                                   'Loss Settlement',
                                                                   'Loss Settlement Building',
                                                                   'Payment basis',
                                                                   'Rating Basis - Dwelling',
                                                                   'Rating Basis - Residence',
                                                                   'Rating Basis -- Dwelling',
                                                                   'Rating Basis -- Residence',
                                                                   'Rating Basis – Dwelling',
                                                                   'Rating Basis – Residence',
                                                                   'Settlement'],
 'homeowners.section_i_property_coverages.inflation_guard_percentage': ['Auto Increase in Insurance',
                                                                        'Automatic Adjustment Of Limits',
                                                                        'Automatic Adjustment Of Limits - '
                                                                        'Annual Increase 3 Percent',
                                                                        'Automatic Adjustment Of Limits -- '
                                                                        'Annual Increase 3 Percent',
                                                                        'Automatic Adjustment Of Limits – '
                                                                        'Annual Increase 3 Percent',
                                                                        'Automatic Increase',
                                                                        'Automatic Increase in Insurance',
                                                                        'Automatic Increase in Insurance - 3 '
                                                                        'Percent',
                                                                        'Automatic Increase in Insurance -- '
                                                                        '3 Percent',
                                                                        'Automatic Increase in Insurance – 3 '
                                                                        'Percent',
                                                                        'Automatic Inflation Protection',
                                                                        'Inflation Guard',
                                                                        'Inflation Protection Coverage',
                                                                        'Percentage Amount',
                                                                        'SM-26 Automatic Increase, RC'],
 'homeowners.section_i_property_coverages.loss_assessment_limit': ['"Residence Premises" - Additional Amount '
                                                                   'Of Insurance',
                                                                   '"Residence Premises" -- Additional '
                                                                   'Amount Of Insurance',
                                                                   '"Residence Premises" – Additional Amount '
                                                                   'Of Insurance',
                                                                   'Homeowner assessments',
                                                                   'Loss Assessment',
                                                                   'Loss Assessment Coverage - Described '
                                                                   'Location - Additional Limit',
                                                                   'Loss Assessment Coverage - Described '
                                                                   'Location -- Additional Limit',
                                                                   'Loss Assessment Coverage - Described '
                                                                   'Location – Additional Limit',
                                                                   'Loss Assessment Coverage - Residence '
                                                                   'Premises',
                                                                   'Loss Assessment Coverage -- Described '
                                                                   'Location - Additional Limit',
                                                                   'Loss Assessment Coverage -- Described '
                                                                   'Location -- Additional Limit',
                                                                   'Loss Assessment Coverage -- Described '
                                                                   'Location – Additional Limit',
                                                                   'Loss Assessment Coverage -- Residence '
                                                                   'Premises',
                                                                   'Loss Assessment Coverage – Described '
                                                                   'Location - Additional Limit',
                                                                   'Loss Assessment Coverage – Described '
                                                                   'Location -- Additional Limit',
                                                                   'Loss Assessment Coverage – Described '
                                                                   'Location – Additional Limit',
                                                                   'Loss Assessment Coverage – Residence '
                                                                   'Premises'],
 'homeowners.section_i_property_coverages.water_backup_and_sump_overflow_limit': ['Added Water Damages '
                                                                                  'Coverage',
                                                                                  'Added Water Damages '
                                                                                  'Coverages',
                                                                                  'Higher Limits - Water '
                                                                                  'Damage Coverage',
                                                                                  'Higher Limits -- Water '
                                                                                  'Damage Coverage',
                                                                                  'Higher Limits – Water '
                                                                                  'Damage Coverage',
                                                                                  'Limited Water Back-up And '
                                                                                  'Sump Discharge Or '
                                                                                  'Overflow Coverage Limit '
                                                                                  'Of Liability',
                                                                                  'Water Back Up And Sump '
                                                                                  'Discharge Or Overflow '
                                                                                  'Coverage',
                                                                                  'Water Backup and Sump '
                                                                                  'Discharge or Overflow'],
 'homeowners.section_i_property_coverages.additional_coverages': ['Additional Coverages',
                                                                  'Additional coverages or conditions',
                                                                  'E. Additional Coverages',
                                                                  'Extra Coverages',
                                                                  'Important notice regarding mold '
                                                                  'remediation expenses',
                                                                  'Property - Additional Coverages',
                                                                  'Property -- Additional Coverages',
                                                                  'Property – Additional Coverages',
                                                                  'Property – Additional Coverages '
                                                                  '(continued)',
                                                                  'Special Limits and Additional Coverages'],
 'homeowners.section_i_property_coverages.additional_coverages[].coverage_name': ['E. Farm Pers. Property',
                                                                                  'F. Farm Barns',
                                                                                  'Farm Barns, Bldgs, & '
                                                                                  'Structures',
                                                                                  'Farm Pers. Property - '
                                                                                  'Scheduled',
                                                                                  'Mold'],
 'homeowners.section_i_property_coverages.additional_coverages[].limit_amount': ['Limit',
                                                                                 'Limit of Liability',
                                                                                 'Section I - Property '
                                                                                 'Coverage Limit Of '
                                                                                 'Liability for the '
                                                                                 'Additional Coverage '
                                                                                 '"Fungi", Wet Or Dry Rot, '
                                                                                 'Or Bacteria'],
 'homeowners.section_i_property_coverages.additional_coverages[].limit_basis': ['Per Loss'],
 'homeowners.section_i_property_coverages.additional_coverages[].sublimit_basis': ['Per Tree'],
 'homeowners.section_i_property_coverages.additional_coverages[].limit_percentage': ['Additional % of '
                                                                                     'damaged covered '
                                                                                     'property limit'],
 'homeowners.section_i_property_coverages.additional_coverages[].limit_increase_amount': ['Amount of '
                                                                                          'Increase'],
 'homeowners.section_i_property_coverages.additional_coverages[].total_limit': ['Total Limit'],
 'homeowners.section_i_property_coverages.coverage_a_dwelling_premium': ['Coverage A',
                                                                         'INCL.',
                                                                         'Incl.',
                                                                         'Included',
                                                                         'PREMIUM'],
 'homeowners.section_i_property_coverages.coverage_b_other_structures_premium': ['INCL.',
                                                                                 'Incl.',
                                                                                 'Included',
                                                                                 'PREMIUM'],
 'homeowners.section_i_property_coverages.coverage_c_personal_property_premium': ['Coverage C',
                                                                                  'INCL.',
                                                                                  'Incl.',
                                                                                  'Included',
                                                                                  'Personal Property',
                                                                                  'PREMIUM'],
 'homeowners.section_i_property_coverages.coverage_d_loss_of_use_premium': ['INCL.',
                                                                            'Incl.',
                                                                            'Included',
                                                                            'PREMIUM'],
 'homeowners.section_i_property_coverages.personal_property_loss_settlement_basis': ['Loss Settlement '
                                                                                     'Contents',
                                                                                     'Payment basis',
                                                                                     'Personal Property '
                                                                                     'Replacement Cost',
                                                                                     'Personal Property '
                                                                                     'Replacement Cost Loss '
                                                                                     'Settlement',
                                                                                     'Rating Basis - '
                                                                                     'Personal Property',
                                                                                     'Rating Basis -- '
                                                                                     'Personal Property',
                                                                                     'Rating Basis – '
                                                                                     'Personal Property'],
 'homeowners.section_i_property_coverages.roof_surfacing_loss_settlement_basis': ['Limited Loss Settlement '
                                                                                  'for Windstorm or Hail '
                                                                                  'Losses to Roof Surfacing'],
 'homeowners.section_i_property_coverages.ordinance_or_law_limit': ['Ordinance and Law Coverage',
                                                                    'Ordinance or Law (25% of Coverage A - '
                                                                    'Dwelling Limit)',
                                                                    'Ordinance or Law (25% of Coverage A -- '
                                                                    'Dwelling Limit)',
                                                                    'Ordinance or Law (25% of Coverage A – '
                                                                    'Dwelling Limit)'],
 'homeowners.section_i_property_coverages.inflation_guard_period': ['AUTOMATIC INFLATION PROTECTION'],
 'homeowners.section_i_property_coverages.inflation_guard_applies_to': ['AUTOMATIC INFLATION PROTECTION'],
 'homeowners.section_i_property_coverages.replacement_cost_insurance_to_value_percentage': ['80% or more of '
                                                                                            'the full '
                                                                                            'replacement '
                                                                                            'cost',
                                                                                            'replacement '
                                                                                            'value of the '
                                                                                            'insured '
                                                                                            'residence',
                                                                                            'Verified '
                                                                                            'replacement '
                                                                                            'cost'],
 'homeowners.section_i_property_coverages.replacement_cost_holdback_threshold': ['less than 5% of the amount '
                                                                                 'of insurance',
                                                                                 'Replacement Cost '
                                                                                 'Provision'],
 'homeowners.section_i_property_coverages.replacement_cost_claim_period_days': ['A claim for any additional '
                                                                                'amount payable under this '
                                                                                'provision',
                                                                                'within 180 days after the '
                                                                                'date of loss',
                                                                                'within 180 days after the '
                                                                                'date of the loss'],
 'homeowners.section_i_property_coverages.renewal_modified_coverages': ['Modifies Coverage(s) at Renewal'],
 'homeowners.section_i_property_coverages.loss_assessment_additional_locations': ['Additional Locations'],
 'homeowners.section_i_property_coverages.loss_assessment_additional_locations[].location': ['Location of '
                                                                                             'Unit or '
                                                                                             'Premises'],
 'homeowners.section_i_property_coverages.loss_assessment_additional_locations[].limit_amount': ['Limit Of '
                                                                                                 'Liability'],
 'homeowners.section_i_property_coverages.loss_assessment_additional_insurance_applies_to': ['Additional '
                                                                                             'Insurance - '
                                                                                             'Residence '
                                                                                             'Premises',
                                                                                             'Additional '
                                                                                             'Insurance -- '
                                                                                             'Residence '
                                                                                             'Premises',
                                                                                             'Additional '
                                                                                             'Insurance – '
                                                                                             'Residence '
                                                                                             'Premises',
                                                                                             'Additional '
                                                                                             'Insurance — '
                                                                                             'Residence '
                                                                                             'Premises'],
 'homeowners.section_i_property_coverages.coverage_b_percentage_of_coverage_a': ['not be more than 10% of '
                                                                                 'the limit of liability '
                                                                                 'that applies to Coverage '
                                                                                 'A'],
 'homeowners.section_i_property_coverages.coverage_d_civil_authority_period': ['Civil Authority Prohibits '
                                                                               'Use'],
 'homeowners.section_i_property_coverages.volcanic_eruption_period_hours': ['Volcanic Eruption Period'],
 'homeowners.section_i_property_coverages.additional_amount_improvement_notice_days': ['SPECIFIED ADDITIONAL '
                                                                                       'AMOUNT OF INSURANCE '
                                                                                       'FOR COVERAGE A - '
                                                                                       'DWELLING'],
 'homeowners.section_i_property_coverages.additional_amount_improvement_threshold_percentage': ['SPECIFIED '
                                                                                                'ADDITIONAL '
                                                                                                'AMOUNT OF '
                                                                                                'INSURANCE '
                                                                                                'FOR '
                                                                                                'COVERAGE A '
                                                                                                '- DWELLING'],
 'homeowners.section_i_property_coverages.personal_property_replacement_cost_holdback_threshold': ['If the '
                                                                                                   'cost to '
                                                                                                   'repair '
                                                                                                   'or '
                                                                                                   'replace '
                                                                                                   'the '
                                                                                                   'property '
                                                                                                   'described '
                                                                                                   'in A. '
                                                                                                   'above is '
                                                                                                   'more '
                                                                                                   'than'],
 'homeowners.section_i_property_coverages.coverage_b_combination_threshold': ['Coverage B-Related Private '
                                                                              'Structures on the Premises'],
 'homeowners.section_i_property_coverages.tree_distance_limit_feet': ['Trees, Plants, Shrubs and Lawns'],
 'homeowners.section_i_property_coverages.farm_personal_property_scheduled_limit': ['E. Farm Pers. Property '
                                                                                    '- Scheduled'],
 'homeowners.section_i_property_coverages.farm_barns_buildings_structures_limit': ['F. Farm Barns, Bldgs, & '
                                                                                   'Structures'],
 'homeowners.section_i_property_coverages.loss_assessment_deductible_sublimit': ['assessments that result '
                                                                                 'from a deductible'],
 'homeowners.section_i_property_coverages.loss_assessment_prior_loss_cap': ['occurred prior to the effective '
                                                                            'date of the policy period'],
 'homeowners.section_i_property_coverages.earthquake_aftershock_period_hours': ['seventy-two hour period'],
 'homeowners.section_i_property_coverages.coverage_c_other_residences_percentage': ['a. Other Residences',
                                                                                    'At your residence not '
                                                                                    'listed in this policy '
                                                                                    'or other policies',
                                                                                    'Other Residences'],
 'homeowners.section_i_property_coverages.coverage_c_other_residences_minimum': ['a. Other Residences',
                                                                                 'Other Residences'],
 'homeowners.section_i_property_coverages.newly_acquired_residence_days': ['newly acquired principal '
                                                                           'residence'],
 'homeowners.section_i_property_coverages.coverage_c_self_storage_percentage': ['b. Self-storage Facilities',
                                                                                'Self-storage Facilities'],
 'homeowners.section_i_property_coverages.coverage_c_self_storage_minimum': ['b. Self-storage Facilities',
                                                                             'Self-storage Facilities'],
 'homeowners.section_ii_liability_coverages': ['Liability',
                                               'Liability Coverage',
                                               'Liability Coverage Section',
                                               'Liability Coverages',
                                               'Personal Liability Coverage',
                                               'Section II',
                                               'Section II - Liability',
                                               'SECTION II - LIABILITY COVERAGES',
                                               'Section II Coverages',
                                               'SECTION II: LIABILITY'],
 'homeowners.section_ii_liability_coverages.coverage_e_personal_liability_limit': ['Amount of liability '
                                                                                   'coverage',
                                                                                   'Cov L',
                                                                                   'Cov L - Personal '
                                                                                   'Liability',
                                                                                   'Cov L -- Personal '
                                                                                   'Liability',
                                                                                   'Cov L – Personal '
                                                                                   'Liability',
                                                                                   'Coverage E',
                                                                                   'Coverage E - Personal '
                                                                                   'Liability',
                                                                                   'Coverage E - Personal '
                                                                                   'Liability - Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E - Personal '
                                                                                   'Liability -- Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E - Personal '
                                                                                   'Liability – Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E -- Personal '
                                                                                   'Liability',
                                                                                   'Coverage E -- Personal '
                                                                                   'Liability - Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E -- Personal '
                                                                                   'Liability -- Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E -- Personal '
                                                                                   'Liability – Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E PERSONAL '
                                                                                   'LIABILITY',
                                                                                   'Coverage E – Personal '
                                                                                   'Liability',
                                                                                   'Coverage E – Personal '
                                                                                   'Liability - Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E – Personal '
                                                                                   'Liability -- Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage E – Personal '
                                                                                   'Liability – Bodily '
                                                                                   'Injury and Property '
                                                                                   'Damage (each occurrence)',
                                                                                   'Coverage L',
                                                                                   'Coverage L - OLT - '
                                                                                   'Premises Liability',
                                                                                   'Coverage L - OLT -- '
                                                                                   'Premises Liability',
                                                                                   'Coverage L - OLT – '
                                                                                   'Premises Liability',
                                                                                   'Coverage L - Personal '
                                                                                   'Liability',
                                                                                   'Coverage L - Premises '
                                                                                   'Liability',
                                                                                   'Coverage L - Premises '
                                                                                   'Liability Coverage (Each '
                                                                                   'Occurrence)',
                                                                                   'Coverage L -- OLT - '
                                                                                   'Premises Liability',
                                                                                   'Coverage L -- OLT -- '
                                                                                   'Premises Liability',
                                                                                   'Coverage L -- OLT – '
                                                                                   'Premises Liability',
                                                                                   'Coverage L -- Personal '
                                                                                   'Liability',
                                                                                   'Coverage L -- Premises '
                                                                                   'Liability',
                                                                                   'Coverage L -- Premises '
                                                                                   'Liability Coverage (Each '
                                                                                   'Occurrence)',
                                                                                   'Coverage L – OLT - '
                                                                                   'Premises Liability',
                                                                                   'Coverage L – OLT -- '
                                                                                   'Premises Liability',
                                                                                   'Coverage L – OLT – '
                                                                                   'Premises Liability',
                                                                                   'Coverage L – Personal '
                                                                                   'Liability',
                                                                                   'Coverage L – Premises '
                                                                                   'Liability',
                                                                                   'Coverage L – Premises '
                                                                                   'Liability Coverage (Each '
                                                                                   'Occurrence)',
                                                                                   'COVERAGE LIMIT',
                                                                                   'E. Personal Liability',
                                                                                   'E: PERSONAL LIABILITY '
                                                                                   'EACH OCCURRENCE',
                                                                                   'Each Occurrence',
                                                                                   'L. Personal Liability',
                                                                                   'L. Personal Liability '
                                                                                   'per Occurence',
                                                                                   'Liability',
                                                                                   'Liability Limit',
                                                                                   'LIMIT',
                                                                                   'LIMIT AMOUNT',
                                                                                   'Limit of Liability',
                                                                                   'Limits',
                                                                                   'Occ',
                                                                                   'PER OCCURRENCE',
                                                                                   'PERSONAL LIABILITY',
                                                                                   'Personal Liability',
                                                                                   'Personal Liability '
                                                                                   'Coverages',
                                                                                   'Personal Liability '
                                                                                   'Occurence',
                                                                                   'Personal Liability per '
                                                                                   'Occurrence'],
 'homeowners.section_ii_liability_coverages.coverage_f_medical_payments_limit': ['Cov M',
                                                                                 'Cov M - Medical Payments',
                                                                                 'Cov M -- Medical Payments',
                                                                                 'Cov M – Medical Payments',
                                                                                 'Coverage F - Medical '
                                                                                 'Payments',
                                                                                 'Coverage F - Medical '
                                                                                 'Payments Coverage',
                                                                                 'Coverage F - Medical '
                                                                                 'Payments to Others',
                                                                                 'Coverage F -- Medical '
                                                                                 'Payments',
                                                                                 'Coverage F -- Medical '
                                                                                 'Payments Coverage',
                                                                                 'Coverage F -- Medical '
                                                                                 'Payments to Others',
                                                                                 'Coverage F – Medical '
                                                                                 'Payments',
                                                                                 'Coverage F – Medical '
                                                                                 'Payments Coverage',
                                                                                 'Coverage F – Medical '
                                                                                 'Payments to Others',
                                                                                 'COVERAGE LIMIT',
                                                                                 'Coverage M',
                                                                                 'Coverage M-Medical '
                                                                                 'Payments to Others',
                                                                                 'F. Medical Payments',
                                                                                 'F: MEDICAL PAYMENTS TO '
                                                                                 'OTHERS',
                                                                                 'Liability Limit',
                                                                                 'LIMIT',
                                                                                 'LIMIT AMOUNT',
                                                                                 'Limit of Liability',
                                                                                 'Limits',
                                                                                 'M. Medical Payments',
                                                                                 'Medical',
                                                                                 'Medical Payments',
                                                                                 'Medical Payments to '
                                                                                 'Others'],
 'homeowners.section_ii_liability_coverages.coverage_f_medical_payments_per_person_limit': ['Coverage F',
                                                                                            'Coverage F - '
                                                                                            'Medical '
                                                                                            'Payments to '
                                                                                            'Others (each '
                                                                                            'person)',
                                                                                            'Coverage F -- '
                                                                                            'Medical '
                                                                                            'Payments to '
                                                                                            'Others (each '
                                                                                            'person)',
                                                                                            'Coverage F '
                                                                                            'MEDICAL '
                                                                                            'PAYMENTS TO '
                                                                                            'OTHERS',
                                                                                            'Coverage F – '
                                                                                            'Medical '
                                                                                            'Payments to '
                                                                                            'Others (each '
                                                                                            'person)',
                                                                                            'COVERAGE LIMIT',
                                                                                            'Coverage M - '
                                                                                            'Medical '
                                                                                            'Payments - Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'Medical '
                                                                                            'Payments -- Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'Medical '
                                                                                            'Payments To '
                                                                                            'Others',
                                                                                            'Coverage M - '
                                                                                            'Medical '
                                                                                            'Payments – Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M - '
                                                                                            'Premises '
                                                                                            'Medical '
                                                                                            'Payments (Each '
                                                                                            'Person)',
                                                                                            'Coverage M -- '
                                                                                            'Medical '
                                                                                            'Payments - Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'Medical '
                                                                                            'Payments -- Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'Medical '
                                                                                            'Payments To '
                                                                                            'Others',
                                                                                            'Coverage M -- '
                                                                                            'Medical '
                                                                                            'Payments – Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M -- '
                                                                                            'Premises '
                                                                                            'Medical '
                                                                                            'Payments (Each '
                                                                                            'Person)',
                                                                                            'Coverage M – '
                                                                                            'Medical '
                                                                                            'Payments - Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'Medical '
                                                                                            'Payments -- Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'Medical '
                                                                                            'Payments To '
                                                                                            'Others',
                                                                                            'Coverage M – '
                                                                                            'Medical '
                                                                                            'Payments – Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT - Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT -- Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay - Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay -- Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'OLT – Premises '
                                                                                            'Med Pay – Per '
                                                                                            'Person',
                                                                                            'Coverage M – '
                                                                                            'Premises '
                                                                                            'Medical '
                                                                                            'Payments (Each '
                                                                                            'Person)',
                                                                                            'Each Person',
                                                                                            'Liability Limit',
                                                                                            'LIMIT',
                                                                                            'LIMIT AMOUNT',
                                                                                            'Limit of '
                                                                                            'Liability',
                                                                                            'Limits',
                                                                                            'M. Medical '
                                                                                            'Payments per '
                                                                                            'Person',
                                                                                            'Medical '
                                                                                            'Payments Per '
                                                                                            'Person',
                                                                                            'MEDICAL '
                                                                                            'PAYMENTS TO '
                                                                                            'OTHERS',
                                                                                            'Per',
                                                                                            'Per Person'],
 'homeowners.section_ii_liability_coverages.coverage_f_medical_payments_per_occurrence_limit': ['Acc',
                                                                                                'COVERAGE '
                                                                                                'LIMIT',
                                                                                                'Coverage M '
                                                                                                '- Medical '
                                                                                                'Payments - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- Medical '
                                                                                                'Payments -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- Medical '
                                                                                                'Payments – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '- Premises '
                                                                                                'Medical '
                                                                                                'Payments '
                                                                                                '(Each '
                                                                                                'Accident)',
                                                                                                'Coverage M '
                                                                                                '-- Medical '
                                                                                                'Payments - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- Medical '
                                                                                                'Payments -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- Medical '
                                                                                                'Payments – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '-- Premises '
                                                                                                'Medical '
                                                                                                'Payments '
                                                                                                '(Each '
                                                                                                'Accident)',
                                                                                                'Coverage M '
                                                                                                '– Medical '
                                                                                                'Payments - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– Medical '
                                                                                                'Payments -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– Medical '
                                                                                                'Payments – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT - '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT -- '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay - '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay -- '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– OLT – '
                                                                                                'Premises '
                                                                                                'Med Pay – '
                                                                                                'Per '
                                                                                                'Occurrence',
                                                                                                'Coverage M '
                                                                                                '– Premises '
                                                                                                'Medical '
                                                                                                'Payments '
                                                                                                '(Each '
                                                                                                'Accident)',
                                                                                                'Liability '
                                                                                                'Limit',
                                                                                                'LIMIT',
                                                                                                'LIMIT '
                                                                                                'AMOUNT',
                                                                                                'Limit of '
                                                                                                'Liability',
                                                                                                'Limits',
                                                                                                'Medical '
                                                                                                'Payments '
                                                                                                'per '
                                                                                                'Occurrence',
                                                                                                'Per Acc',
                                                                                                'Per '
                                                                                                'Accident',
                                                                                                'Per '
                                                                                                'Occurrence'],
 'homeowners.section_ii_liability_coverages.damage_to_property_of_others_limit': ['Damage To Property Of '
                                                                                  'Others',
                                                                                  'Damaged property'],
 'homeowners.section_ii_liability_coverages.additional_coverages': ['Defense coverages',
                                                                    "Employer's liability for residence "
                                                                    'employees',
                                                                    'Extra Coverages',
                                                                    'Liability - Additional Coverages',
                                                                    'Liability -- Additional Coverages',
                                                                    'Liability – Additional Coverages',
                                                                    'SECTION II - ADDITIONAL COVERAGES'],
 'homeowners.section_ii_liability_coverages.additional_coverages[].coverage_name': ['D. Loss Assessment',
                                                                                    'Loss Assessment',
                                                                                    'Personal Injury'],
 'homeowners.section_ii_liability_coverages.additional_coverages[].limit_amount': ['Limit'],
 'homeowners.section_ii_liability_coverages.additional_coverages[].aggregate_limit_amount': ['Section II - '
                                                                                             'Coverage E '
                                                                                             'Aggregate '
                                                                                             'Sublimit of '
                                                                                             'Liability for '
                                                                                             '"Fungi", Wet '
                                                                                             'Or Dry Rot, Or '
                                                                                             'Bacteria'],
 'homeowners.section_ii_liability_coverages.additional_coverages[].premium': ['Premium'],
 'homeowners.section_ii_liability_coverages.coverage_e_personal_liability_premium': ['Coverage L',
                                                                                     'INCL.',
                                                                                     'Incl.',
                                                                                     'Included',
                                                                                     'Personal Liability',
                                                                                     'PREMIUM'],
 'homeowners.section_ii_liability_coverages.coverage_f_medical_payments_premium': ['Coverage M',
                                                                                   'INCL.',
                                                                                   'Incl.',
                                                                                   'Included',
                                                                                   'Medical Payments',
                                                                                   'PREMIUM'],
 'homeowners.section_ii_liability_coverages.liability_coverage_type': ['Liability Coverage',
                                                                       'Premises Liability Coverage'],
 'homeowners.section_ii_liability_coverages.coverage_e_limit_increase': ['The limit of liability shown for '
                                                                         'Coverage L — Personal Liability is '
                                                                         'increased by'],
 'homeowners.section_ii_liability_coverages.coverage_f_limit_increase': ['The limit of liability shown for '
                                                                         'Coverage M - Medical Payments to '
                                                                         'Others is increased by',
                                                                         'The limit of liability shown for '
                                                                         'Coverage M -- Medical Payments to '
                                                                         'Others is increased by',
                                                                         'The limit of liability shown for '
                                                                         'Coverage M – Medical Payments to '
                                                                         'Others is increased by',
                                                                         'The limit of liability shown for '
                                                                         'Coverage M-Medical Payments to '
                                                                         'Others is increased by'],
 'homeowners.section_ii_liability_coverages.damage_to_property_of_others_limit_increase': ['The limit of '
                                                                                           'liability shown '
                                                                                           'for Damage To '
                                                                                           'Property Of '
                                                                                           'Others is '
                                                                                           'increased by'],
 'homeowners.section_ii_liability_coverages.covered_exposures': ['Home'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].exposure_type': ['Home',
                                                                                 'Incidental Business'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].coverage': ['Coverage L - Personal Liability '
                                                                            'and Coverage M - Medical '
                                                                            'Payments to Others Applies'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].exposure_number': ['No'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].address.line_1': ['Location'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].address.city': ['City'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].address.state': ['St'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].address.postal_code': ['Zip'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].address.county': ['County'],
 'homeowners.section_ii_liability_coverages.covered_exposures[].number_of_families': ['No Fam'],
 'homeowners.section_ii_liability_coverages.medical_expense_period_years': ['incurred or medically '
                                                                            'ascertained within',
                                                                            'within three years'],
 'homeowners.section_ii_liability_coverages.business_compensation_threshold': ['"Business"',
                                                                               '"Incidental business at '
                                                                               'home"',
                                                                               '"Incidental business away '
                                                                               'from home"'],
 'homeowners.section_ii_liability_coverages.business_compensation_period_months': ['"Business"'],
 'homeowners.section_ii_liability_coverages.intentional_damage_min_age': ['C. Damage To Property Of Others'],
 'homeowners.section_ii_liability_coverages.excluded_animal_types': ['Animal Exclusion - New York',
                                                                     'Animal Exclusion -- New York',
                                                                     'Animal Exclusion – New York'],
 'homeowners.section_ii_liability_coverages.max_dogs_permitted': ['More than three dogs'],
 'homeowners.section_ii_liability_coverages.swimming_pool_fence_min_height_inches': ['Swimming Pool '
                                                                                     'Liability Endorsement'],
 'homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds': ['Horsepower',
                                                                             'Motor Vehicle Liability',
                                                                             'Watercraft',
                                                                             'Watercraft Liability'],
 'homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.toy_vehicle_max_mph': ['Motorized '
                                                                                                 'land '
                                                                                                 'vehicles'],
 'homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_length_ft': ['Large '
                                                                                                  'watercraft'],
 'homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_engine_hp': ['Large '
                                                                                                  'watercraft'],
 'homeowners.section_ii_liability_coverages.vehicle_watercraft_thresholds.watercraft_rental_max_days': ['Large '
                                                                                                        'watercraft'],
 'homeowners.section_ii_liability_coverages.coverage_f_medical_payments_per_occurrence_premium': ['Coverage '
                                                                                                  'M - OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M - OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '- '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '- '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '- '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '– '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '– '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M -- OLT '
                                                                                                  '– '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT - '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT '
                                                                                                  '-- '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay - '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay '
                                                                                                  '-- Per '
                                                                                                  'Occurrence',
                                                                                                  'Coverage '
                                                                                                  'M – OLT – '
                                                                                                  'Premises '
                                                                                                  'Med Pay – '
                                                                                                  'Per '
                                                                                                  'Occurrence',
                                                                                                  'INCL.',
                                                                                                  'Incl.',
                                                                                                  'Included',
                                                                                                  'PREMIUM'],
 'homeowners.section_ii_liability_coverages.residence_employee_hours_threshold': ['"Residential staff" means',
                                                                                  'WHO IS COVERED'],
 'homeowners.section_ii_liability_coverages.damage_to_property_of_others_statement_days': ['C. Duties After '
                                                                                           '"Occurrence"'],
 'homeowners.deductibles': ['Deductible(s)',
                            'Deductibles',
                            'Peril Deductible',
                            'SECTION I - DEDUCTIBLES',
                            'Section I Deductibles'],
 'homeowners.deductibles.all_other_perils_deductible': ['All Other Perils',
                                                        'All Other Perils Deductible',
                                                        'Base deductible',
                                                        'Deductible',
                                                        'Policy Deductible',
                                                        'Property Coverage Deductible',
                                                        'Property Coverage Deductible (All Other Perils)',
                                                        'Property Deductible'],
 'homeowners.deductibles.wind_hail_deductible': ['Wind Deductible', 'Windstorm or Hail Deductible'],
 'homeowners.deductibles.named_storm_deductible': ['Named Storm Deductible'],
 'homeowners.deductibles.disappearing_deductible': ['Disappearing Deductible'],
 'homeowners.deductibles.all_other_perils_deductible_type': ['Deductible Type'],
 'homeowners.deductibles.named_storm_deductible_percentage': ['Named Storm Deductible',
                                                              'Named Storm Percentage Deductible'],
 'homeowners.deductibles.water_backup_deductible': ['Water Back Up And Sump Discharge Or Overflow Coverage '
                                                    'Deductible',
                                                    'Water backup deductible',
                                                    'water backup special deductible'],
 'homeowners.deductibles.deductible_waiver_threshold': ['Base deductible waived for losses greater than',
                                                        'Waived for losses greater than'],
 'homeowners.deductibles.named_storm_period_end_hours': ['Ending 24 hours following'],
 'homeowners.rating_characteristics': ['Rating Criteria', 'SUPPLEMENTAL DECLARATIONS AND RATING INFORMATION'],
 'homeowners.rating_characteristics.distance_to_fire_station': ['Distance to Fire Department',
                                                                'Distance to Station',
                                                                'mi to FD',
                                                                'Miles From Fire Dept',
                                                                'Miles to Fire Department',
                                                                'MILES TO FIRE DEPT',
                                                                'Miles to Fire Station'],
 'homeowners.rating_characteristics.territorial_zone': ['Rating Zone',
                                                        'Territorial Zone',
                                                        'Territory',
                                                        'Zone'],
 'homeowners.rating_characteristics.policy_tier': ['Policy Tier', 'Tier'],
 'homeowners.rating_characteristics.premium_group': ['PREM GROUP', 'Premium Group'],
 'homeowners.rating_characteristics.vandalism_malicious_mischief_option': ['Vandalism'],
 'homeowners.scheduled_personal_property': ['IM-175 - PERSONAL ARTICLES COVERAGE',
                                            'NYCM INLAND MARINE SCHEDULE'],
 'homeowners.scheduled_personal_property[].item_number': ['ID'],
 'homeowners.scheduled_personal_property[].class_description': ['JEWELRY', 'SILVERWARE'],
 'homeowners.scheduled_personal_property[].item_description': ['DESCRIPTION'],
 'homeowners.scheduled_personal_property[].scheduled_limit': ['VALUE'],
 'homeowners.scheduled_personal_property[].appraisal_date': ['APPR. DATE'],
 'homeowners.scheduled_personal_property[].serial_number': ['SERIAL #'],
 'homeowners.scheduled_personal_property[].class_total_amount': ['JEWELRY Total Amount',
                                                                 'SILVERWARE Total Amount',
                                                                 'TOTAL AMOUNT',
                                                                 'TOTAL AMOUNT JEWELRY',
                                                                 'TOTAL AMOUNT SILVERWARE'],
 'homeowners.scheduled_personal_property[].in_vault': ['In-vault jewelry'],
 'homeowners.scheduled_personal_property[].form_total_amount': ['TOTAL AMOUNT IM-175 - PERSONAL ARTICLES '
                                                                'COVERAGE'],
 'homeowners.optional_endorsement_coverages': ['ADDITIONAL / OPTIONAL COVERAGES', 'Optional Coverages'],
 'homeowners.optional_endorsement_coverages[].coverage_name': ['Additional Replacement Cost',
                                                               'Personal Property Replacement Cost'],
 'homeowners.optional_endorsement_coverages[].coverage_description': ['COVERAGE DESCRIPTION'],
 'homeowners.optional_endorsement_coverages[].form_reference': ['Endorsement'],
 'homeowners.optional_endorsement_coverages[].applies_to': ['For Location'],
 'homeowners.optional_endorsement_coverages[].limit_amount': ['Limit',
                                                              'Limit of Liability',
                                                              'On Premises',
                                                              'Per Occurrence Limit',
                                                              'Underground Utility Line Coverage Per '
                                                              'Occurrence Limit',
                                                              'We insure, for up to',
                                                              'We pay no more than',
                                                              'We pay up to'],
 'homeowners.optional_endorsement_coverages[].aggregate_limit_amount': ['Annual Aggregate Limit'],
 'homeowners.optional_endorsement_coverages[].deductible_amount': ['Deductible',
                                                                   'ITEM IV. DEDUCTIBLE',
                                                                   'Per Occurrence Deductible',
                                                                   'Underground Utility Line Coverage Per '
                                                                   'Occurrence Deductible'],
 'homeowners.optional_endorsement_coverages[].premium': ['Premium'],
 'homeowners.optional_endorsement_coverages[].is_included': ['Included'],
 'homeowners.optional_endorsement_coverages[].off_premises_limit_amount': ['Off Premises'],
 'homeowners.optional_endorsement_coverages[].extensions': ['EXTENSION OF COVERAGE',
                                                            'EXTENSIONS OF COVERAGE'],
 'homeowners.optional_endorsement_coverages[].per_day_limit_amount': ['up to a maximum payment of'],
 'homeowners.optional_endorsement_coverages[].total_payment_cap_amount': ['Total payment for lost income is '
                                                                          'not to exceed'],
 'homeowners.optional_endorsement_coverages[].consequential_loss_radius_feet': ['Consequential Losses'],
 'homeowners.optional_endorsement_coverages[].notice_days': ['Send to us, within'],
 'homeowners.discounts': ['Credits / Debits',
                          'Discount(s)',
                          'DISCOUNTS',
                          'Discounts and Surcharges',
                          'Modifications and Credits Information',
                          'Overview',
                          'Premium Adjustment',
                          'Premium Discount Summary',
                          'Surcharge Information',
                          'The following discounts reduced your premium',
                          'Your Discount'],
 'homeowners.discounts[].discount_name': ['ABS Discount',
                                          'Accident Prevention Course Discount',
                                          'ANTI-LOCK BRAKES',
                                          'Anti-Lock Braking System (ABS) Discount',
                                          'ANTI-THEFT DEVICE',
                                          'Credit or Surcharge for Coverage A - Deductible',
                                          'CUSTOMIZING',
                                          'DAYTIME RUNNING LAMPS',
                                          'DESCRIPTION',
                                          'Fire Protective Device',
                                          'HOME OWNERSHIP',
                                          'Loss Free Credit',
                                          'Multi Policy Credit',
                                          'Multi-Car Discount',
                                          'Multi-Vehicle Discount',
                                          'NEW CAR DISCOUNT',
                                          'New Home Credit',
                                          'PASSIVE RESTRAINT',
                                          'Premises Alarm'],
 'homeowners.discounts[].amount': ['PREMIUM', 'SAVINGS'],
 'homeowners.discounts[].form_reference': ['FORM NAME'],
 'homeowners.discounts[].edition_date': ['EDITION'],
 'homeowners.discounts[].reason': ['Reason for Premium Adjustment'],
 'homeowners.discounts[].location_reference': ['Loc #/Bldg #'],
 'homeowners.mortgagees': ['Mortgage Data',
                           'Mortgagee Information',
                           'Mortgagee Name and Address',
                           'Mortgagee or Secured Party',
                           'MORTGAGEE(S)',
                           'Mortgagee(s) or Secured Party'],
 'homeowners.mortgagees[].rank': ['1st Mortgagee',
                                  'First',
                                  'FIRST MORTGAGEE',
                                  'Mortgage Data – First',
                                  'Mortgagee #1',
                                  'Mortgagee #2',
                                  'Mortgagee #3',
                                  'Number',
                                  'ORDER'],
 'homeowners.mortgagees[].name': ['Mortgagee Company Name',
                                  'Mortgagee Name',
                                  'Name and Address',
                                  'NAME/ADDRESS'],
 'homeowners.mortgagees[].address.line_1': ['Address'],
 'homeowners.mortgagees[].address.city': ['City', 'City, State, Zip'],
 'homeowners.mortgagees[].address.state': ['St'],
 'homeowners.mortgagees[].address.postal_code': ['Zip'],
 'homeowners.mortgagees[].loan_number': ['Loan #', 'Loan Number'],
 'homeowners.mortgagees[].clause_type': ['Its Successors and/or Assigns',
                                         'Its successors and/or assigns As their interest may appear'],
 'homeowners.mortgagees[].description_of_interest': ['Interest'],
 'homeowners.mortgagees[].is_payor': ['Bill Mortgagee', 'Billed'],
 'homeowners.mortgagees[].status': ['STATUS'],
 'homeowners.mortgagees[].cancellation_notice_days': ['Mortgage Clause',
                                                      'Mortgagee Clause',
                                                      'Mortgagee or loss payee',
                                                      'Secured Party Coverage'],
 'homeowners.mortgagees[].location_reference': ['Loc'],
 'homeowners.mortgagees[].proof_of_loss_days': ['L. Mortgage Clause',
                                                'Mortgage Clause',
                                                'Mortgagee Clause',
                                                'Mortgagee or loss payee',
                                                'Secured Party Coverage'],
 'homeowners.special_limits_of_liability': ['Limitations on Certain Property',
                                            'Personal Property - Special Limits of Liability',
                                            'Personal Property – Special Limits of Liability',
                                            'Special limits',
                                            'Special Limits of Liability'],
 'homeowners.special_limits_of_liability[].class_description': ['antennas, tapes, wires, records, disks',
                                                                'Appliances',
                                                                'Away from Premises',
                                                                'bank notes, bullion',
                                                                'Business Property',
                                                                'Business Property Away from Insured Premise',
                                                                'Business Property Away from Insured '
                                                                'Premises',
                                                                'Business Property on Insured Premises',
                                                                'Camper Bodies',
                                                                'Collectible stamps, coins, and medals',
                                                                'Dismounted Camper Bodies on Insured '
                                                                'Premises',
                                                                'Electronic',
                                                                'Electronic Apparatus in/upon vehicle',
                                                                'Electronic Equipment',
                                                                'Electronic Equipment Property on Insured '
                                                                'Premises',
                                                                'Firearms',
                                                                'firearms and related equipment',
                                                                'Furs that are lost, misplaced, or stolen',
                                                                'Golf carts',
                                                                'Grave Markers',
                                                                'Grave markers or mausoleums',
                                                                'Gun and Gun Accessories',
                                                                'Guns',
                                                                'Guns that are lost, misplaced, or stolen',
                                                                'Home Computers',
                                                                'Jewelry',
                                                                'Jewelry and Furs',
                                                                'Jewelry, watches or precious and '
                                                                'semi-precious stones, whether set or unset, '
                                                                'that are lost, misplaced, or stolen',
                                                                'Legal tender, bank notes, stored value '
                                                                'cards',
                                                                'Legal tender, bank notes, stored value '
                                                                'cards, bullion, gold, silver, platinum, '
                                                                'tokens, unrecoverable scrip, smart cards, '
                                                                'prepaid value cards, prepaid debit cards, '
                                                                'or gift certificates',
                                                                'Money',
                                                                'Money, Bank Notes, Bullion',
                                                                'Money, Coins',
                                                                'Motorized Vehicles',
                                                                'Plated ware, silverware, goldware, '
                                                                'pewterware, tableware, trays, trophies',
                                                                'Plated ware, silverware, goldware, '
                                                                'pewterware, tableware, trays, trophies, and '
                                                                'other household and personal articles, '
                                                                'other than jewelry and articles described '
                                                                'in another Special Limit category, that '
                                                                'consist principally of sterling silver, '
                                                                'gold, or pewter that are lost, misplaced, '
                                                                'or stolen',
                                                                'portable electronic equipment',
                                                                'Securities',
                                                                'Securities, Commercial Paper',
                                                                'Securities, Commercial Paper, etc',
                                                                'Securities, deeds, evidences of debt, '
                                                                'letters of credit, notes other than bank '
                                                                'notes, manuscripts, passports, or tickets',
                                                                'Securities, Stamps',
                                                                'Silverware',
                                                                'Tapes, records, discs or other media '
                                                                'in/upon vehicle',
                                                                'Trailer',
                                                                'Trailers',
                                                                'trailers or semitrailers',
                                                                'Watercraft',
                                                                'Watercraft Including Trailer',
                                                                'Watercraft, including their furnishings, '
                                                                'equipment, and outboard motors'],
 'homeowners.special_limits_of_liability[].base_limit': ['Base Insurance',
                                                         'Base Limit',
                                                         'Limit',
                                                         'Limit of Liability'],
 'homeowners.special_limits_of_liability[].increased_limit': ['Additional Insurance',
                                                              'Amount of Increase',
                                                              'Increased Insurance',
                                                              'Increased Limit'],
 'homeowners.special_limits_of_liability[].premium': ['Premium'],
 'homeowners.scheduled_other_structures[].structure_number': ['No'],
 'homeowners.scheduled_other_structures[].structure_description': ['Describe',
                                                                   'Description',
                                                                   'Description of Structure',
                                                                   'Garage',
                                                                   'Identification of Structure',
                                                                   'Structure'],
 'homeowners.scheduled_other_structures[].limit_amount': ['Amount of Insurance', 'Limit'],
 'homeowners.scheduled_other_structures[].deductible_amount': ['Deductible'],
 'homeowners.scheduled_other_structures[].premium': ['Item Premium', 'Premium'],
 'homeowners.scheduled_other_structures[].location_reference': ['Location'],
 'homeowners.scheduled_locations': ['ADDITIONAL LOCATION DETAILS',
                                    'Coverage Declaration for Location #',
                                    'Coverage Information for Location',
                                    'Coverages',
                                    'For the following location(s)',
                                    'For your location(s)',
                                    'Insured Location Summary',
                                    'LOCATION COVERAGES',
                                    'LOCATION DESCRIPTION',
                                    'Location Summary',
                                    'Rating Information',
                                    'Supplemental Policy Declarations for Location #'],
 'homeowners.scheduled_locations[].location_number': ['LOC',
                                                      'Loc. #',
                                                      'Location',
                                                      'LOCATION NUMBER',
                                                      'Location Number',
                                                      'NUMBER',
                                                      'Property'],
 'homeowners.scheduled_locations[].location_reference': ['Required Rating Information'],
 'homeowners.scheduled_locations[].building_number': ['Building'],
 'homeowners.scheduled_locations[].description': ['Described Location',
                                                  'For Location',
                                                  'Location Description and Address',
                                                  'Supplemental Declarations',
                                                  'Supplemental Schedule'],
 'homeowners.scheduled_locations[].address': ['Location Description and Address'],
 'homeowners.scheduled_locations[].address.line_1': ['ADDRESS',
                                                     'LOCATION ADDRESS (if different than mailing address)',
                                                     'Street'],
 'homeowners.scheduled_locations[].address.city': ['City'],
 'homeowners.scheduled_locations[].address.state': ['State'],
 'homeowners.scheduled_locations[].address.postal_code': ['Zip'],
 'homeowners.scheduled_locations[].address.county': ['COUNTY', 'County', 'County Name'],
 'homeowners.scheduled_locations[].address.county_code': ['County Code'],
 'homeowners.scheduled_locations[].address.sub_county': ['SUB COUNTY', 'Sub County'],
 'homeowners.scheduled_locations[].occupancy_type': ['Occupancy', 'Occupancy Type'],
 'homeowners.scheduled_locations[].usage_type': ['Dwelling Use',
                                                 'Is this primary residence of the insured?',
                                                 'LOC TYPE',
                                                 'Owner Occupied',
                                                 'Primary Residence',
                                                 'Risk Description',
                                                 'Seasonal',
                                                 'Seasonal/Secondary',
                                                 'Secondary',
                                                 'SECONDARY INDICATOR',
                                                 'Usage'],
 'homeowners.scheduled_locations[].dwelling_type': ['Residence Type Code', 'Type of Home'],
 'homeowners.scheduled_locations[].construction_type': ['Construction', 'Construction Type'],
 'homeowners.scheduled_locations[].year_built': ['Construction Year', 'Year Built', 'Year of Construction'],
 'homeowners.scheduled_locations[].number_of_stories': ['# of Stories'],
 'homeowners.scheduled_locations[].square_footage': ['Square Footage'],
 'homeowners.scheduled_locations[].number_of_families': ['# of Families',
                                                         'Families',
                                                         'No Fam',
                                                         'No. of Families',
                                                         'Number of Families',
                                                         'NumberofFamilies'],
 'homeowners.scheduled_locations[].protection_class': ['Fire Protection',
                                                       'Fire Protection Class',
                                                       'PROT CLASS',
                                                       'Protection',
                                                       'Protection Class',
                                                       'Semi Protected',
                                                       'Unprotected'],
 'homeowners.scheduled_locations[].territory_code': ['GL Territory', 'Rating Territory', 'TERR', 'Territory'],
 'homeowners.scheduled_locations[].territorial_zone': ['Rating Zone',
                                                       'TERR',
                                                       'Territorial Zone',
                                                       'Territory',
                                                       'Zone'],
 'homeowners.scheduled_locations[].territorial_subzone': ['Sub Zone', 'Sub-Zone', 'SubZone'],
 'homeowners.scheduled_locations[].fire_district': ['Fire District'],
 'homeowners.scheduled_locations[].feet_from_hydrant': ['Distance to Fire Hydrant',
                                                        'Distance to Hydrant',
                                                        'Feet From Hydrant',
                                                        'Feet to Hydrant',
                                                        'ft to hydrant'],
 'homeowners.scheduled_locations[].distance_to_fire_station': ['Distance to Fire Department',
                                                               'Distance to Station',
                                                               'mi to FD',
                                                               'Miles From Fire Dept',
                                                               'Miles to Fire Department',
                                                               'MILES TO FIRE DEPT',
                                                               'Miles to Fire Station'],
 'homeowners.scheduled_locations[].alarm_type': ['What type of system?'],
 'homeowners.scheduled_locations[].section_i_property_coverages': ['Coverage Information',
                                                                   'Coverages and Limits of Liability',
                                                                   'Policy Coverage',
                                                                   'Policy Coverages',
                                                                   'Property Coverage Section',
                                                                   'Property Coverages',
                                                                   'Section I',
                                                                   'Section I - Property',
                                                                   'SECTION I - PROPERTY COVERAGES',
                                                                   'Section I Coverages',
                                                                   'SECTION I: PROPERTY DAMAGE'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_a_dwelling_limit': ['A. Dwelling',
                                                                                             'A. Residence',
                                                                                             'A: DWELLING',
                                                                                             'Cov A',
                                                                                             'Cov A - '
                                                                                             'Dwelling',
                                                                                             'Cov A -- '
                                                                                             'Dwelling',
                                                                                             'Cov A – '
                                                                                             'Dwelling',
                                                                                             'Coverage A',
                                                                                             'Coverage A - '
                                                                                             'Dwelling',
                                                                                             'Coverage A - '
                                                                                             'Residence',
                                                                                             'Coverage A -- '
                                                                                             'Dwelling',
                                                                                             'Coverage A -- '
                                                                                             'Residence',
                                                                                             'Coverage A '
                                                                                             'DWELLING',
                                                                                             'Coverage A '
                                                                                             'Dwelling',
                                                                                             'Coverage A – '
                                                                                             'Dwelling',
                                                                                             'Coverage A – '
                                                                                             'Residence',
                                                                                             'COVERAGE LIMIT',
                                                                                             'Deluxe House '
                                                                                             'Coverage',
                                                                                             'DWELLING',
                                                                                             'House',
                                                                                             'Liability '
                                                                                             'Limit',
                                                                                             'LIMIT',
                                                                                             'LIMIT AMOUNT',
                                                                                             'Limit of '
                                                                                             'Liability',
                                                                                             'Limits',
                                                                                             'Residence'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_b_other_structures_limit': ['Appurtenant '
                                                                                                     'Structures',
                                                                                                     'B. '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'B. '
                                                                                                     'Private '
                                                                                                     'Structures',
                                                                                                     'B. '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures',
                                                                                                     'B: '
                                                                                                     'OTHER '
                                                                                                     'STRUCTURES',
                                                                                                     'Cov B',
                                                                                                     'Cov B '
                                                                                                     '- '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Cov B '
                                                                                                     '-- '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Cov B '
                                                                                                     '– '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B',
                                                                                                     'Coverage '
                                                                                                     'B - '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B - '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B - '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures '
                                                                                                     'on the '
                                                                                                     'Premises',
                                                                                                     'Coverage '
                                                                                                     'B -- '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B -- '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B -- '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures '
                                                                                                     'on the '
                                                                                                     'Premises',
                                                                                                     'Coverage '
                                                                                                     'B '
                                                                                                     'OTHER '
                                                                                                     'STRUCTURES',
                                                                                                     'Coverage '
                                                                                                     'B – '
                                                                                                     'Other '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B – '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures',
                                                                                                     'Coverage '
                                                                                                     'B – '
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures '
                                                                                                     'on the '
                                                                                                     'Premises',
                                                                                                     'COVERAGE '
                                                                                                     'LIMIT',
                                                                                                     'Liability '
                                                                                                     'Limit',
                                                                                                     'LIMIT',
                                                                                                     'LIMIT '
                                                                                                     'AMOUNT',
                                                                                                     'Limit '
                                                                                                     'of '
                                                                                                     'Liability',
                                                                                                     'Limits',
                                                                                                     'Other '
                                                                                                     'permanent '
                                                                                                     'structures',
                                                                                                     'OTHER '
                                                                                                     'STRUCTURES',
                                                                                                     'Related '
                                                                                                     'Private '
                                                                                                     'Structures'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_c_personal_property_limit': ['C. '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'C: '
                                                                                                      'PERSONAL '
                                                                                                      'PROPERTY',
                                                                                                      'Contents',
                                                                                                      'Cov C',
                                                                                                      'Cov C '
                                                                                                      '- '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Cov C '
                                                                                                      '-- '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Cov C '
                                                                                                      '– '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Coverage '
                                                                                                      'C',
                                                                                                      'Coverage '
                                                                                                      'C - '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Coverage '
                                                                                                      'C -- '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Coverage '
                                                                                                      'C '
                                                                                                      'PERSONAL '
                                                                                                      'PROPERTY',
                                                                                                      'Coverage '
                                                                                                      'C – '
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'COVERAGE '
                                                                                                      'LIMIT',
                                                                                                      'Deluxe '
                                                                                                      'Contents '
                                                                                                      'Coverage',
                                                                                                      'Deluxe '
                                                                                                      'or '
                                                                                                      'Standard '
                                                                                                      'Contents',
                                                                                                      'Liability '
                                                                                                      'Limit',
                                                                                                      'LIMIT',
                                                                                                      'LIMIT '
                                                                                                      'AMOUNT',
                                                                                                      'Limit '
                                                                                                      'of '
                                                                                                      'Liability',
                                                                                                      'Limits',
                                                                                                      'PERSONAL '
                                                                                                      'PROPERTY',
                                                                                                      'Personal '
                                                                                                      'Property',
                                                                                                      'Unscheduled '
                                                                                                      'Personal '
                                                                                                      'Property'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_d_loss_of_use_limit': ["Add'l "
                                                                                                'Living Exp. '
                                                                                                '& Loss of '
                                                                                                'Rent',
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense',
                                                                                                'Additional '
                                                                                                'living '
                                                                                                'expenses',
                                                                                                'Cov D',
                                                                                                'Cov D - '
                                                                                                'Addl Living '
                                                                                                'Exp/Loss of '
                                                                                                'Rents',
                                                                                                'Cov D -- '
                                                                                                'Addl Living '
                                                                                                'Exp/Loss of '
                                                                                                'Rents',
                                                                                                'Cov D – '
                                                                                                'Addl Living '
                                                                                                'Exp/Loss of '
                                                                                                'Rents',
                                                                                                'Coverage D',
                                                                                                'Coverage D '
                                                                                                '- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Costs And '
                                                                                                'Loss Of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense and '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense or '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '- Addl. '
                                                                                                'Living Exp '
                                                                                                'and Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '- Loss of '
                                                                                                'Use',
                                                                                                'Coverage D '
                                                                                                '-- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Costs And '
                                                                                                'Loss Of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '-- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense and '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '-- '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense or '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '-- Addl. '
                                                                                                'Living Exp '
                                                                                                'and Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '-- Loss of '
                                                                                                'Use',
                                                                                                'Coverage D '
                                                                                                'LOSS OF USE',
                                                                                                'Coverage D '
                                                                                                '– '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Costs And '
                                                                                                'Loss Of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '– '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense and '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '– '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expense or '
                                                                                                'Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '– Addl. '
                                                                                                'Living Exp '
                                                                                                'and Loss of '
                                                                                                'Rent',
                                                                                                'Coverage D '
                                                                                                '– Loss of '
                                                                                                'Use',
                                                                                                'COVERAGE '
                                                                                                'LIMIT',
                                                                                                "D. Add'l "
                                                                                                'Living Exp. '
                                                                                                '& Loss of '
                                                                                                'Rent',
                                                                                                'D. '
                                                                                                'Additional '
                                                                                                'Living '
                                                                                                'Expenses',
                                                                                                'D. Living '
                                                                                                'Exp. & Loss '
                                                                                                'of Rent',
                                                                                                'D. Loss Of '
                                                                                                'Use',
                                                                                                'D: LOSS OF '
                                                                                                'USE',
                                                                                                'Liability '
                                                                                                'Limit',
                                                                                                'LIMIT',
                                                                                                'LIMIT '
                                                                                                'AMOUNT',
                                                                                                'Limit of '
                                                                                                'Liability',
                                                                                                'Limits',
                                                                                                'Loss of '
                                                                                                'Rents',
                                                                                                'LOSS OF USE',
                                                                                                'Loss Of Use '
                                                                                                '(Cov. D)'],
 'homeowners.scheduled_locations[].section_i_property_coverages.loss_settlement_basis': ['ACTUAL CASH VALUE',
                                                                                         'Actual Cash Value '
                                                                                         'Provision',
                                                                                         'Loss Settlement',
                                                                                         'Loss Settlement '
                                                                                         'Building',
                                                                                         'Payment basis',
                                                                                         'Rating Basis - '
                                                                                         'Dwelling',
                                                                                         'Rating Basis - '
                                                                                         'Residence',
                                                                                         'Rating Basis -- '
                                                                                         'Dwelling',
                                                                                         'Rating Basis -- '
                                                                                         'Residence',
                                                                                         'Rating Basis – '
                                                                                         'Dwelling',
                                                                                         'Rating Basis – '
                                                                                         'Residence',
                                                                                         'Settlement'],
 'homeowners.scheduled_locations[].section_i_property_coverages.inflation_guard_percentage': ['Auto Increase '
                                                                                              'in Insurance',
                                                                                              'Automatic '
                                                                                              'Adjustment Of '
                                                                                              'Limits',
                                                                                              'Automatic '
                                                                                              'Adjustment Of '
                                                                                              'Limits - '
                                                                                              'Annual '
                                                                                              'Increase 3 '
                                                                                              'Percent',
                                                                                              'Automatic '
                                                                                              'Adjustment Of '
                                                                                              'Limits -- '
                                                                                              'Annual '
                                                                                              'Increase 3 '
                                                                                              'Percent',
                                                                                              'Automatic '
                                                                                              'Adjustment Of '
                                                                                              'Limits – '
                                                                                              'Annual '
                                                                                              'Increase 3 '
                                                                                              'Percent',
                                                                                              'Automatic '
                                                                                              'Increase',
                                                                                              'Automatic '
                                                                                              'Increase in '
                                                                                              'Insurance',
                                                                                              'Automatic '
                                                                                              'Increase in '
                                                                                              'Insurance - 3 '
                                                                                              'Percent',
                                                                                              'Automatic '
                                                                                              'Increase in '
                                                                                              'Insurance -- '
                                                                                              '3 Percent',
                                                                                              'Automatic '
                                                                                              'Increase in '
                                                                                              'Insurance – 3 '
                                                                                              'Percent',
                                                                                              'Automatic '
                                                                                              'Inflation '
                                                                                              'Protection',
                                                                                              'Inflation '
                                                                                              'Guard',
                                                                                              'Inflation '
                                                                                              'Protection '
                                                                                              'Coverage',
                                                                                              'Percentage '
                                                                                              'Amount',
                                                                                              'SM-26 '
                                                                                              'Automatic '
                                                                                              'Increase, RC'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_a_dwelling_premium': ['Coverage A',
                                                                                               'INCL.',
                                                                                               'Incl.',
                                                                                               'Included',
                                                                                               'PREMIUM'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_b_other_structures_premium': ['INCL.',
                                                                                                       'Incl.',
                                                                                                       'Included',
                                                                                                       'PREMIUM'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_c_personal_property_premium': ['Coverage '
                                                                                                        'C',
                                                                                                        'INCL.',
                                                                                                        'Incl.',
                                                                                                        'Included',
                                                                                                        'Personal '
                                                                                                        'Property',
                                                                                                        'PREMIUM'],
 'homeowners.scheduled_locations[].section_i_property_coverages.coverage_d_loss_of_use_premium': ['INCL.',
                                                                                                  'Incl.',
                                                                                                  'Included',
                                                                                                  'PREMIUM'],
 'homeowners.scheduled_locations[].section_i_property_coverages.personal_property_loss_settlement_basis': ['Loss '
                                                                                                           'Settlement '
                                                                                                           'Contents',
                                                                                                           'Payment '
                                                                                                           'basis',
                                                                                                           'Personal '
                                                                                                           'Property '
                                                                                                           'Replacement '
                                                                                                           'Cost',
                                                                                                           'Personal '
                                                                                                           'Property '
                                                                                                           'Replacement '
                                                                                                           'Cost '
                                                                                                           'Loss '
                                                                                                           'Settlement',
                                                                                                           'Rating '
                                                                                                           'Basis '
                                                                                                           '- '
                                                                                                           'Personal '
                                                                                                           'Property',
                                                                                                           'Rating '
                                                                                                           'Basis '
                                                                                                           '-- '
                                                                                                           'Personal '
                                                                                                           'Property',
                                                                                                           'Rating '
                                                                                                           'Basis '
                                                                                                           '– '
                                                                                                           'Personal '
                                                                                                           'Property'],
 'homeowners.scheduled_locations[].section_ii_liability_coverages': ['Liability Coverage',
                                                                     'Liability Coverage Section',
                                                                     'Liability Coverages',
                                                                     'Section II',
                                                                     'Section II - Liability',
                                                                     'SECTION II - LIABILITY COVERAGES',
                                                                     'Section II Coverages',
                                                                     'SECTION II: LIABILITY'],
 'homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_e_personal_liability_limit': ['Amount '
                                                                                                         'of '
                                                                                                         'liability '
                                                                                                         'coverage',
                                                                                                         'Cov '
                                                                                                         'L',
                                                                                                         'Cov '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Cov '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Cov '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'E',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '-- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '– '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '-- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '– '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         'PERSONAL '
                                                                                                         'LIABILITY',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '-- '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'E '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         '– '
                                                                                                         'Bodily '
                                                                                                         'Injury '
                                                                                                         'and '
                                                                                                         'Property '
                                                                                                         'Damage '
                                                                                                         '(each '
                                                                                                         'occurrence)',
                                                                                                         'Coverage '
                                                                                                         'L',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'OLT '
                                                                                                         '- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'OLT '
                                                                                                         '-- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'OLT '
                                                                                                         '– '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '- '
                                                                                                         'Premises '
                                                                                                         'Liability '
                                                                                                         'Coverage '
                                                                                                         '(Each '
                                                                                                         'Occurrence)',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'OLT '
                                                                                                         '- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'OLT '
                                                                                                         '-- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'OLT '
                                                                                                         '– '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '-- '
                                                                                                         'Premises '
                                                                                                         'Liability '
                                                                                                         'Coverage '
                                                                                                         '(Each '
                                                                                                         'Occurrence)',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'OLT '
                                                                                                         '- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'OLT '
                                                                                                         '-- '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'OLT '
                                                                                                         '– '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'Premises '
                                                                                                         'Liability',
                                                                                                         'Coverage '
                                                                                                         'L '
                                                                                                         '– '
                                                                                                         'Premises '
                                                                                                         'Liability '
                                                                                                         'Coverage '
                                                                                                         '(Each '
                                                                                                         'Occurrence)',
                                                                                                         'COVERAGE '
                                                                                                         'LIMIT',
                                                                                                         'E. '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'E: '
                                                                                                         'PERSONAL '
                                                                                                         'LIABILITY '
                                                                                                         'EACH '
                                                                                                         'OCCURRENCE',
                                                                                                         'Each '
                                                                                                         'Occurrence',
                                                                                                         'L. '
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'L. '
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         'per '
                                                                                                         'Occurence',
                                                                                                         'Liability',
                                                                                                         'Liability '
                                                                                                         'Limit',
                                                                                                         'LIMIT',
                                                                                                         'LIMIT '
                                                                                                         'AMOUNT',
                                                                                                         'Limit '
                                                                                                         'of '
                                                                                                         'Liability',
                                                                                                         'Limits',
                                                                                                         'Occ',
                                                                                                         'PER '
                                                                                                         'OCCURRENCE',
                                                                                                         'PERSONAL '
                                                                                                         'LIABILITY',
                                                                                                         'Personal '
                                                                                                         'Liability',
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         'Coverages',
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         'Occurence',
                                                                                                         'Personal '
                                                                                                         'Liability '
                                                                                                         'per '
                                                                                                         'Occurrence'],
 'homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_f_medical_payments_limit': ['Cov '
                                                                                                       'M',
                                                                                                       'Cov '
                                                                                                       'M - '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Cov '
                                                                                                       'M -- '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Cov '
                                                                                                       'M – '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Coverage '
                                                                                                       'F - '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Coverage '
                                                                                                       'F - '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'Coverage',
                                                                                                       'Coverage '
                                                                                                       'F - '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'to '
                                                                                                       'Others',
                                                                                                       'Coverage '
                                                                                                       'F -- '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Coverage '
                                                                                                       'F -- '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'Coverage',
                                                                                                       'Coverage '
                                                                                                       'F -- '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'to '
                                                                                                       'Others',
                                                                                                       'Coverage '
                                                                                                       'F – '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Coverage '
                                                                                                       'F – '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'Coverage',
                                                                                                       'Coverage '
                                                                                                       'F – '
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'to '
                                                                                                       'Others',
                                                                                                       'COVERAGE '
                                                                                                       'LIMIT',
                                                                                                       'Coverage '
                                                                                                       'M',
                                                                                                       'Coverage '
                                                                                                       'M-Medical '
                                                                                                       'Payments '
                                                                                                       'to '
                                                                                                       'Others',
                                                                                                       'F. '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'F: '
                                                                                                       'MEDICAL '
                                                                                                       'PAYMENTS '
                                                                                                       'TO '
                                                                                                       'OTHERS',
                                                                                                       'Liability '
                                                                                                       'Limit',
                                                                                                       'LIMIT',
                                                                                                       'LIMIT '
                                                                                                       'AMOUNT',
                                                                                                       'Limit '
                                                                                                       'of '
                                                                                                       'Liability',
                                                                                                       'Limits',
                                                                                                       'M. '
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Medical',
                                                                                                       'Medical '
                                                                                                       'Payments',
                                                                                                       'Medical '
                                                                                                       'Payments '
                                                                                                       'to '
                                                                                                       'Others'],
 'homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_f_medical_payments_per_person_limit': ['Coverage '
                                                                                                                  'F',
                                                                                                                  'Coverage '
                                                                                                                  'F '
                                                                                                                  '- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'to '
                                                                                                                  'Others '
                                                                                                                  '(each '
                                                                                                                  'person)',
                                                                                                                  'Coverage '
                                                                                                                  'F '
                                                                                                                  '-- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'to '
                                                                                                                  'Others '
                                                                                                                  '(each '
                                                                                                                  'person)',
                                                                                                                  'Coverage '
                                                                                                                  'F '
                                                                                                                  'MEDICAL '
                                                                                                                  'PAYMENTS '
                                                                                                                  'TO '
                                                                                                                  'OTHERS',
                                                                                                                  'Coverage '
                                                                                                                  'F '
                                                                                                                  '– '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'to '
                                                                                                                  'Others '
                                                                                                                  '(each '
                                                                                                                  'person)',
                                                                                                                  'COVERAGE '
                                                                                                                  'LIMIT',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'To '
                                                                                                                  'Others',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '(Each '
                                                                                                                  'Person)',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'To '
                                                                                                                  'Others',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '(Each '
                                                                                                                  'Person)',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'To '
                                                                                                                  'Others',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '-- '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '-- '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'OLT '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Med '
                                                                                                                  'Pay '
                                                                                                                  '– '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'Coverage '
                                                                                                                  'M '
                                                                                                                  '– '
                                                                                                                  'Premises '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  '(Each '
                                                                                                                  'Person)',
                                                                                                                  'Each '
                                                                                                                  'Person',
                                                                                                                  'Liability '
                                                                                                                  'Limit',
                                                                                                                  'LIMIT',
                                                                                                                  'LIMIT '
                                                                                                                  'AMOUNT',
                                                                                                                  'Limit '
                                                                                                                  'of '
                                                                                                                  'Liability',
                                                                                                                  'Limits',
                                                                                                                  'M. '
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'per '
                                                                                                                  'Person',
                                                                                                                  'Medical '
                                                                                                                  'Payments '
                                                                                                                  'Per '
                                                                                                                  'Person',
                                                                                                                  'MEDICAL '
                                                                                                                  'PAYMENTS '
                                                                                                                  'TO '
                                                                                                                  'OTHERS',
                                                                                                                  'Per',
                                                                                                                  'Per '
                                                                                                                  'Person'],
 'homeowners.scheduled_locations[].section_ii_liability_coverages.coverage_f_medical_payments_per_occurrence_limit': ['Acc',
                                                                                                                      'COVERAGE '
                                                                                                                      'LIMIT',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '(Each '
                                                                                                                      'Accident)',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '(Each '
                                                                                                                      'Accident)',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '-- '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '-- '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'OLT '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Med '
                                                                                                                      'Pay '
                                                                                                                      '– '
                                                                                                                      'Per '
                                                                                                                      'Occurrence',
                                                                                                                      'Coverage '
                                                                                                                      'M '
                                                                                                                      '– '
                                                                                                                      'Premises '
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      '(Each '
                                                                                                                      'Accident)',
                                                                                                                      'Liability '
                                                                                                                      'Limit',
                                                                                                                      'LIMIT',
                                                                                                                      'LIMIT '
                                                                                                                      'AMOUNT',
                                                                                                                      'Limit '
                                                                                                                      'of '
                                                                                                                      'Liability',
                                                                                                                      'Limits',
                                                                                                                      'Medical '
                                                                                                                      'Payments '
                                                                                                                      'per '
                                                                                                                      'Occurrence',
                                                                                                                      'Per '
                                                                                                                      'Acc',
                                                                                                                      'Per '
                                                                                                                      'Accident',
                                                                                                                      'Per '
                                                                                                                      'Occurrence'],
 'homeowners.scheduled_locations[].deductibles': ['Deductible(s)',
                                                  'Deductibles',
                                                  'Peril Deductible',
                                                  'SECTION I - DEDUCTIBLES',
                                                  'Section I Deductibles'],
 'homeowners.scheduled_locations[].deductibles.all_other_perils_deductible': ['All Other Perils',
                                                                              'All Other Perils Deductible',
                                                                              'Base deductible',
                                                                              'Deductible',
                                                                              'Policy Deductible',
                                                                              'Property Coverage Deductible',
                                                                              'Property Deductible'],
 'homeowners.scheduled_locations[].deductibles.wind_hail_deductible': ['Wind Deductible',
                                                                       'Windstorm or Hail Deductible'],
 'homeowners.scheduled_locations[].deductibles.deductible_waiver_threshold': ['Base deductible waived for '
                                                                              'losses greater than',
                                                                              'Waived for losses greater '
                                                                              'than'],
 'homeowners.scheduled_locations[].deductibles.water_backup_deductible': ['Water Back Up And Sump Discharge '
                                                                          'Or Overflow Coverage Deductible',
                                                                          'Water backup deductible',
                                                                          'water backup special deductible'],
 'homeowners.scheduled_locations[].applicable_forms': ['Applicable Forms', 'Coverage Endorsements'],
 'homeowners.scheduled_locations[].applicable_forms[].form_number': ['Form',
                                                                     'Form #',
                                                                     'FORM NAME',
                                                                     'Form No.',
                                                                     'Form no.',
                                                                     'Form Number',
                                                                     'NAME'],
 'homeowners.scheduled_locations[].applicable_forms[].edition_date': ['Ed.',
                                                                      'EDITION',
                                                                      'Edition',
                                                                      'Edition Date',
                                                                      'FORM EDITION',
                                                                      'Rev.'],
 'homeowners.scheduled_locations[].applicable_forms[].form_title': ['Description', 'Form Name', 'Title'],
 'homeowners.scheduled_locations[].applicable_forms[].premium': ['Cost', 'PREMIUM', 'Premium'],
 'homeowners.scheduled_locations[].applicable_forms[].is_included': ['Incl', 'Incl.'],
 'homeowners.scheduled_locations[].applicable_forms[].limit_amount': ['COVERAGE LIMIT', 'Limit'],
 'homeowners.scheduled_locations[].premium': ['PREMIUM',
                                              'Property Total',
                                              'Total Annual Premium for Location #',
                                              'Total Annual Premium This Location',
                                              'TOTAL LOCATION PREMIUM'],
 'homeowners.scheduled_locations[].acreage': ['Acreage'],
 'homeowners.scheduled_locations[].causes_of_loss_form': ['Causes of Loss Form'],
 'homeowners.scheduled_locations[].deductible_type': ['Deductible Type'],
 'homeowners.scheduled_locations[].solid_fuel_burning_device_present': ['Solid Fuel Burning Device(s)'],
 'homeowners.scheduled_locations[].swimming_pool': ['Pool',
                                                    'SWIMMING POOL',
                                                    'Swimming Pool',
                                                    'Swimming Pool, Dock or Beach'],
 'homeowners.scheduled_locations[].property_premium': ['Premium including Fire Fee'],
 'homeowners.scheduled_locations[].inland_marine_premium': ['Inland Marine Premium'],
 'homeowners.scheduled_locations[].discounts': ['Credits / Debits'],
 'homeowners.scheduled_locations[].discounts[].discount_name': ['ABS Discount',
                                                                'Accident Prevention Course Discount',
                                                                'ANTI-LOCK BRAKES',
                                                                'Anti-Lock Braking System (ABS) Discount',
                                                                'ANTI-THEFT DEVICE',
                                                                'Credit or Surcharge for Coverage A - '
                                                                'Deductible',
                                                                'CUSTOMIZING',
                                                                'DAYTIME RUNNING LAMPS',
                                                                'DESCRIPTION',
                                                                'HOME OWNERSHIP',
                                                                'Multi-Car Discount',
                                                                'Multi-Vehicle Discount',
                                                                'NEW CAR DISCOUNT',
                                                                'New Home Credit',
                                                                'PASSIVE RESTRAINT'],
 'homeowners.scheduled_locations[].discounts[].discount_type': ['Credit',
                                                                'Discount',
                                                                'Discounts and Surcharges',
                                                                'Surcharge'],
 'homeowners.scheduled_locations[].discounts[].amount': ['PREMIUM', 'SAVINGS'],
 'homeowners.scheduled_locations[].policy_form_number': ['BASIC FORM'],
 'homeowners.scheduled_locations[].program_name': ['SPECIAL PROGRAM'],
 'homeowners.scheduled_locations[].related_policy_number': ['PRIMARY POLICY NUMBER',
                                                            'Seasonal Policy Number'],
 'homeowners.scheduled_locations[].townhouse_rowhouse_indicator': ['TOWN/ROW HOUSE', 'Town/Row House'],
 'homeowners.scheduled_locations[].doublewide_indicator': ['DOUBLEWIDE', 'Doublewide'],
 'homeowners.scheduled_locations[].number_of_units': ['# of Apartments',
                                                      'Number of Apartments',
                                                      'NUMBER OF UNITS'],
 'homeowners.scheduled_locations[].units_between_fire_walls': ['# Units between Fire Walls',
                                                               'UNITS BETWEEN FIRE WALLS'],
 'homeowners.scheduled_locations[].lead_abatement': ['LEAD ABATEMENT', 'Lead Abatement'],
 'homeowners.scheduled_locations[].certificate_of_occupancy_date': ['CERTIFICATE OF OCCUPANCY DATE'],
 'homeowners.scheduled_locations[].months_occupied_annually': ['MONTHS OCCUPIED ANNUALLY'],
 'homeowners.scheduled_locations[].roof_updated_within_20_years': ['Has the roof been updated in the last 20 '
                                                                   'years?',
                                                                   'ROOF RENOVATIONS'],
 'homeowners.scheduled_locations[].roof_year_installed': ['ROOF INSTALLATION YEAR',
                                                          'Year Of Installation',
                                                          'Year Roof Updated'],
 'homeowners.scheduled_locations[].heating_type': ['PRIMARY HEAT SOURCE',
                                                   'Primary Heat Source',
                                                   'Primary Heating Type'],
 'homeowners.scheduled_locations[].heating_installation_year': ['PRIMARY HEAT INSTALLATION YEAR'],
 'homeowners.scheduled_locations[].secondary_heating_type': ['ALTERNATE HEAT SOURCE',
                                                             'Any Other Secondary Heating Source?',
                                                             'Secondary Heating Type'],
 'homeowners.scheduled_locations[].basement_type': ['Basement',
                                                    'Basement Construction',
                                                    'FOUNDATION TYPE',
                                                    'Foundation Type'],
 'homeowners.scheduled_locations[].fuel_tank_location': ['FUEL TANK LOCATION'],
 'homeowners.scheduled_locations[].gated_community': ['GATED COMMUNITY'],
 'homeowners.scheduled_locations[].renovation.heating_year': ['Renov Heat'],
 'homeowners.scheduled_locations[].renovation.roof_year': ['Renov Roof'],
 'homeowners.scheduled_locations[].renovation.heating_updated': ['HEAT_YN'],
 'homeowners.scheduled_locations[].renovation.roof_updated': ['ROOF_YN'],
 'homeowners.scheduled_locations[].renovation.plumbing_updated': ['PLUMBING_YN'],
 'homeowners.scheduled_locations[].renovation.electrical_updated': ['ELECTRIC_YN'],
 'homeowners.scheduled_locations[].premium_group': ['PREM GROUP', 'Premium Group'],
 'homeowners.scheduled_locations[].roof_to_wall_attachment': ['Roof to Wall Attachment'],
 'homeowners.scheduled_locations[].opening_protection': ['Opening Protection'],
 'homeowners.scheduled_locations[].roof_shape': ['Hip Roof'],
 'homeowners.scheduled_personal_property_total': ['TOTAL IM SCHEDULE'],
 'homeowners.valuable_articles_classes': ['Blanket coverage', 'Itemized articles', 'Valuable Articles'],
 'homeowners.valuable_articles_classes[].class_description': ['Class'],
 'homeowners.valuable_articles_classes[].blanket_amount': ['Amount of blanket coverage'],
 'homeowners.valuable_articles_classes[].blanket_per_item_limit': ['Blanket limit per item'],
 'homeowners.valuable_articles_classes[].itemized_amount': ['Amount of itemized coverage', 'Total Amount'],
 'homeowners.valuable_articles_classes[].market_value_cap_percentage': ['Partial loss', 'Total loss'],
 'homeowners.roof_surfacing_loss_schedule': ['Roof Surfacing Loss Percentage Table'],
 'homeowners.roof_surfacing_loss_schedule[].roof_age_years': ['Age of Roof (in Years)'],
 'homeowners.roof_surfacing_loss_schedule[].roof_material': ['Architectural Shingle',
                                                             'Asphalt Shingle',
                                                             'Built Up/Roll',
                                                             'Metal',
                                                             'Other',
                                                             'Slate',
                                                             'Tile',
                                                             'Type of Roof Surfacing Material',
                                                             'Wood'],
 'homeowners.seasonal_rental': ['Seasonal Rentals Surcharge'],
 'homeowners.seasonal_rental[].number_of_weeks_rented': ['Number of Weeks Rented'],
 'homeowners.seasonal_rental[].waterfront_property': ['Waterfront Property'],
 'homeowners.seasonal_rental[].watercraft_offered_with_rental': ['Watercraft Offered With Rental'],
 'homeowners.seasonal_rental[].recreational_vehicles_offered_with_rental': ['Recreational Vehicles (Other '
                                                                            'Than Watercraft) Offered with '
                                                                            'Rental'],
 'homeowners.seasonal_rental[].trampoline_on_premises': ['Trampoline on Premises'],
 'homeowners.value_added_services[].service_name': ['"FREE" IDENTITY THEFT RESOLUTION SERVICES'],
 'homeowners.value_added_services[].provider': ['CyberScout'],
 'homeowners.value_added_services[].phone': ['call Erie and Niagara at'],
 'homeowners.value_added_services[].website': ['Access to our educational web site'],
 'homeowners.valuable_articles_extra_coverages': ['Defective title',
                                                  'Extra Coverages',
                                                  'Fine art on loan or consignment',
                                                  'Jewelry on loan or consignment',
                                                  'Jewelry works in progress',
                                                  'Newly acquired valuable articles',
                                                  'Works in progress'],
 'homeowners.form_provisions': ['"Incidental farming"',
                                '"Residence premises conditional business liability"',
                                'Conditional replacement cost',
                                'Construction deductible',
                                'Extended replacement cost',
                                'Limited ability to rebuild',
                                'Musical and photographic articles used for profit',
                                'Pursuit or holding of public office',
                                'Vacant house deductible'],
 'homeowners.form_provisions[].provision_name': ['"Incidental farming"',
                                                 '"Residence premises conditional business liability"',
                                                 '"Unoccupied" means',
                                                 'At your residence not listed in this policy or other '
                                                 'policies',
                                                 'Conditional replacement cost',
                                                 'Construction deductible',
                                                 'Extended replacement cost',
                                                 'Freezing water',
                                                 'Limited ability to rebuild',
                                                 'Musical and photographic articles used for profit',
                                                 'Pursuit or holding of public office',
                                                 'Vacant house deductible'],
 'underwriting.prior_insurance.carrier_name': ['Previous Insurance Carrier'],
 'underwriting.prior_insurance.expiration_date': ['Previous Policy Expiration Date'],
 'underwriting.prior_insurance.notes': ['explain "Other"', 'Please explain "Other"'],
 'underwriting.prior_cancellation_or_refusal': ['Has any company cancelled, non-renewed or refused insurance '
                                                '(including non-payment of premium) for this applicant?'],
 'underwriting.other_policies_with_carrier': ['Does Insured have other policies with Dryden Mutual?'],
 'underwriting.prior_underwriting_approval': ['Was prior approval given from underwriting for this risk?'],
 'underwriting.agency_visual_inspection': ['Has this property been visually inspected by agency staff?'],
 'underwriting.overall_risk_condition': ['Overall condition of the risk'],
 'underwriting.has_commercial_policy_for_business': ['Is there a commercial policy for this exposure?'],
 'underwriting.application_questions': ['Application Questions',
                                        'General Information',
                                        'Liability Questions',
                                        'Property Questions',
                                        'Secondary/Seasonal Home'],
 'underwriting.insurance_scores': ['INSURANCE SCORE INFORMATION'],
 'underwriting.insurance_scores[].insured_name': ['NAME'],
 'underwriting.insurance_scores[].ordered_date': ['ORDERED DATE'],
 'underwriting.insurance_scores[].report_vendor': ['REPORT'],
 'underwriting.insurance_scores[].coded_score': ['CODED SCORE'],
 'underwriting.exceptions': ['EXCEPTIONS'],
 'underwriting.exceptions[].level': ['LEVEL'],
 'underwriting.exceptions[].exception_type': ['TYPE'],
 'underwriting.exceptions[].original_value': ['ORIGINAL VALUE'],
 'underwriting.exceptions[].overridden_value': ['OVERRIDDEN VALUE'],
 'underwriting.consumer_report_disclosures': ['Adverse Action Notice',
                                              'Adverse Action Notice - Home',
                                              'Extraordinary Life Event',
                                              'Fair Credit Notice',
                                              'FAIR CREDIT REPORTING ACT NOTICE',
                                              'IMPORTANT INFORMATION ABOUT THE COST OF YOUR INSURANCE – USE '
                                              'OF CONSUMER REPORTS',
                                              'Important Messages and Details'],
 'underwriting.consumer_report_disclosures[].reporting_agency': ['comes from', 'obtained from'],
 'underwriting.consumer_report_disclosures[].reference_number': ['Reference Number'],
 'underwriting.consumer_report_disclosures[].adverse_action_factors': ['The following is a list of one to '
                                                                       'four credit factors that had the '
                                                                       'greatest impact upon your consumer '
                                                                       'report information'],
 'underwriting.consumer_report_disclosures[].reporting_agency_address': ['Please contact them at'],
 'underwriting.consumer_report_disclosures[].form_reference': ['FORM'],
 'underwriting.prior_losses_last_5_years': ['Any previous property or liability losses, whether or not paid '
                                            'by insurance during the last 5 years, on any owned or '
                                            'previously owned risk in which you have or had an insured '
                                            'interest?']}

ALIASES_REMOVED = {'document.applicable_coverages': ['Applicable Coverage(s)', 'Other Coverage(s) As Specified'],
 'document.transaction_reason': ['Amended Date', 'Modifies Coverage(s) at Renewal'],
 'policy.effective_date': ['Inception Date'],
 'named_insured.mailing_address': ['Mail To'],
 'premium.basic_premium': ['Premium At Inception'],
 'signature.title': ['Authorized Representative', 'Our Authorized Representative'],
 'homeowners.section_ii_liability_coverages.coverage_e_personal_liability_limit': ['Section II - Liability'],
 'homeowners.special_limits_of_liability[].class_description': ['Special Limits of Liability']}

SOURCE_NOTE = '2026-09-24: 409 fields added from a 69-PDF / 11-carrier homeowners gap analysis; misplaced aliases moved (Inception Date, Mail To, Amended Date, Modifies Coverage(s) at Renewal, Authorized Representative, Applicable Coverage(s)). Applied directly to this file: the generator scripts named in fideon:note are not in this repo. Second pass (same day, stricter re-review of every page): +212 fields, section/list/column-header aliases, form-embedded thresholds (claim, appraisal, liberalization, watercraft/vehicle, vacancy), per-building copies of dwelling and coverage detail in scheduled_locations[]; underwriting.consumer_report_disclosure became consumer_report_disclosures[]. Third pass: +19 fields; scheduled_locations[] blocks inherit the aliases of their top-level twins; hyphen/en-dash/double-dash variants of coverage labels; column headers (LIMIT, PREMIUM, Limit of Liability) sit on every field they span; a few labels (Appraisal, Policy period, Secured Party Coverage, Payment basis) deliberately name two sibling fields because one printed clause carries both values. Fourth pass: final residual labels; every mix of hyphen/en dash/double hyphen in coverage labels; fields previously covered only by a heading now carry their own label. Fifth pass (independent, value-first review of every page): 33 fields added; wrong aliases fixed (Premium At Inception is the total policy premium; Mortgagee Clause, Who is providing this notice?, Watercraft, PAGE, Special Limits of Liability re-homed). Refinement: merged duplicate fields (homeowners.dwelling.distance_to_fire_station -> homeowners.rating_characteristics.distance_to_fire_station; homeowners.dwelling.distance_to_hydrant -> homeowners.rating_characteristics.feet_from_hydrant; homeowners.dwelling.vacancy_threshold_days -> homeowners.dwelling.vacancy_thresholds[].days; homeowners.dwelling.number_of_weeks_rented -> homeowners.seasonal_rental[].number_of_weeks_rented; homeowners.scheduled_locations[].number_of_weeks_rented -> homeowners.seasonal_rental[].number_of_weeks_rented); every field annotated with fideon:value_type and a generated description.'

# ── 5. blocks carried over as-is ────────────────────────────────────────────
# main's prose convention (config/policy_check/dwelling_fire.json): keyed fields
# hold the values, these hold every other printed word, so nothing the page
# prints is missing from the gold.
VERBATIM_PROPERTIES = {'additional_fields': {'type': 'array',
                       'description': 'Printed label/value pairs that have no dedicated field above, kept as '
                                      'key and value: the label as the document prints it, the section '
                                      'heading it sits under, and the value as a FieldValue (raw, parsed, '
                                      'page_ref).',
                       'items': {'type': 'object',
                                 'properties': {'section': {'type': ['string', 'null']},
                                                'label': {'type': 'string'},
                                                'value': {'$ref': '#/$defs/FieldValue'}},
                                 'required': ['label', 'value']}},
 'text_sections': {'type': 'object', 'additionalProperties': {'$ref': '#/$defs/TextSection'}},
 'printed_lines': {'type': 'array',
                   'description': 'Printed lines that no keyed field, label or prose section already '
                                  'carries: section headings, column headers, captions, page headers and '
                                  'footers, empty labels. Together with the keyed fields and text_sections, '
                                  'nothing the page prints is missing from the gold.',
                   'items': {'type': 'object',
                             'properties': {'page': {'type': 'integer'},
                                            'kind': {'type': 'string',
                                                     'enum': ['heading',
                                                              'caption',
                                                              'header',
                                                              'footer',
                                                              'row']},
                                            'cells': {'type': 'array', 'items': {'type': 'string'}}},
                             'required': ['page', 'kind', 'cells']}}}

VERBATIM_DEFS = {'TextSection': {'type': 'object',
                 'description': 'A block of printed text exactly as the document carries it: a prose '
                                "paragraph, notice, condition or disclaimer, or the page's remaining "
                                'label/footer text. Nothing the page prints is left out of the gold; '
                                'structured fields above hold the values, these hold the words.',
                 'properties': {'section_id': {'type': 'string'},
                                'section_title': {'type': ['string', 'null']},
                                'section_type': {'type': 'string', 'enum': ['prose', 'other']},
                                'raw_text': {'type': 'string'},
                                'page_range': {'type': 'array', 'items': {'type': 'integer'}},
                                'form_number': {'type': ['string', 'null']}},
                 'required': ['section_id', 'raw_text', 'page_range']}}

# ── 4. value types and descriptions ─────────────────────────────────────────
SCOPE_NOTES = {
    "premium.premium_by_coverage_part": "Coverage/limit/premium table rows as printed. The named per-coverage "
                                         "fields (section_i/section_ii *_premium, *_limit) hold the same values "
                                         "in fixed slots; fill both when the document prints such a table.",
    "homeowners.form_provisions": "Catch-all for numeric terms printed inside policy forms that have no "
                                  "dedicated field. Use a dedicated field first when one exists.",
}


MONEY_END = ("_amount", "_limit", "_premium", "_fee", "_tax", "_surcharge", "_deductible", "_price",
             "_value", "_cap", "_sublimit", "_threshold")
INT_END = ("_days", "_months", "_years", "_hours", "_weeks", "_count", "_feet", "_ft", "_mph", "_hp",
           "_inches", "_age", "_year", "_minutes")
DATE_WORDS = ("_date", "date_of_", "_datetime", "timestamp", "_time")



TEXT_NAMES = {"edition_date", "new_value", "old_value", "identifier_value", "can_limit", "time_limit",
              "coverage_parts_present", "number_of_weeks_rented", "company_shares", "limit_basis",
              "sublimit_basis", "deductible_basis", "valuation_basis", "rating_basis"}
YES_NO_NAMES = {"disappearing_deductible", "roof_updated_within_20_years", "prior_losses_last_5_years"}


def value_type(name):
    n = name
    if n in TEXT_NAMES or n.endswith(("_basis", "_threshold", "_type", "_description", "_name", "_reference")):
        return "text"
    if n in YES_NO_NAMES:
        return "yes_no"
    if n in ("signed_date", "signed_datetime"):
        return "datetime"
    if "percentage" in n or n.endswith("_percent") or n.endswith("_pct") or n == "percentage":
        return "percentage"
    if any(w in n for w in DATE_WORDS) or n in ("anniversary_date", "effective_date", "expiration_date"):
        return "datetime" if ("time" in n and "date" not in n) else "date"
    if n.startswith(("is_", "has_")) or n.endswith(("_indicator", "_present", "_updated", "_applied")) or \
            n in ("sprinklered", "swimming_pool", "trampoline", "dogs_on_premises", "flagged", "is_payor",
                  "is_included", "is_excluded", "is_mandatory", "gated_community", "lead_abatement",
                  "waterfront_property", "visibility", "principal_unit_at_risk", "pipes_winterized",
                  "accessible_year_round", "occupied_by_others", "business_on_premises",
                  "thermostat_controlled_central_heat", "slab_foundation", "is_signed",
                  "not_a_bill_indicator", "in_vault"):
        return "yes_no"
    if n.startswith("number_of_") or n.endswith(INT_END) or n in ("year_built", "page_count", "page_number",
                                                                    "total_locations", "points", "occurrence_count",
                                                                    "exposure_count", "dog_number", "dogs_count",
                                                                    "max_dogs_permitted", "term_sequence",
                                                                    "number_of_risks", "garage_number_of_cars",
                                                                    "policy_term_months", "rank"):
        return "integer" if n != "rank" else "text"
    if n.endswith(MONEY_END) or n in ("premium", "amount", "total_policy_premium", "basic_premium",
                                       "surplus_lines_tax", "fire_fee", "broker_fee", "amount_due",
                                       "amount_enclosed", "market_value", "replacement_cost_value",
                                       "purchase_price", "cost_of_improvements", "paid_amount",
                                       "reserved_amount", "group_premium", "total_value", "base_limit",
                                       "increased_limit", "total_limit", "scheduled_limit", "deductible",
                                       "blanket_amount", "itemized_amount", "minimum_amount", "maximum_amount"):
        return "money"
    return "text"



def human(name):
    t = name.replace("_", " ").strip()
    for a, b in ((" pct", " percentage"), ("naic", "NAIC"), ("fein", "FEIN"), ("ssn", "SSN"), (" id", " ID"),
                 ("coverage a", "Coverage A"), ("coverage b", "Coverage B"), ("coverage c", "Coverage C"),
                 ("coverage d", "Coverage D"), ("coverage e", "Coverage E"), ("coverage f", "Coverage F"),
                 ("ho ", "HO "), ("url", "URL")):
        t = re.sub(r"\b%s\b" % re.escape(a.strip()), b.strip(), t) if a.strip() else t
    return t[:1].upper() + t[1:]


TYPE_TEXT = {"money": "Money amount; parsed is the number (negative for credits), null for Incl./***/N/A.",
             "date": "Date; parsed is MM/DD/YYYY (see fideon:parsed_formats).",
             "datetime": "Time or date-time as printed; parsed normalised where possible.",
             "percentage": "Percentage; parsed is the number (10% -> 10).",
             "integer": "Whole number (count, days, years...); parsed is the number.",
             "yes_no": "Yes/No indicator; parsed is \"Yes\" or \"No\" (never a JSON boolean).",
             "text": "Text as printed."}


def describe(path, node, section_names):
    name = path.rsplit(".", 1)[-1].replace("[]", "")
    where = " / ".join(human(p.replace("[]", "")) for p in section_names) if section_names else "document root"
    al = node.get("fideon:aliases", [])
    printed = (" Printed as e.g. %s." % ", ".join('"%s"' % a for a in al[:4])) if al else ""
    return human(name), where, printed




def _alias_key(a):
    return (a.lower(), a)


def _container(schema, path):
    """The properties dict that holds the last segment of ``path``."""
    node = schema
    for seg in path.split(".")[:-1]:
        many = seg.endswith("[]")
        node = node["properties"][seg[:-2] if many else seg]
        if many:
            node = node["items"]
    return node["properties"]


def _node(schema, path):
    name = path.split(".")[-1]
    return _container(schema, path)[name[:-2] if name.endswith("[]") else name]


def _new(kind):
    if kind == "field":
        return dict(REF)
    if kind == "object":
        return {"type": "object", "properties": {}}
    if kind == "list_obj":
        return {"type": "array", "items": {"type": "object", "properties": {}}}
    return {"type": "array", "items": dict(REF)}


def _walk(schema):
    """(path, node, kind) for every field, section and list, in document order."""
    out = []

    def w(n, p):
        if "$ref" in n:
            out.append((p, n, "field"))
        elif n.get("type") == "object":
            out.append((p, n, "object"))
            for k, v in n["properties"].items():
                w(v, "%s.%s" % (p, k) if p else k)
        elif n.get("type") == "array":
            it = n["items"]
            if "$ref" in it:
                out.append((p, n, "list_scalar"))
            else:
                out.append((p, n, "list_obj"))
                for k, v in it["properties"].items():
                    w(v, "%s[].%s" % (p, k))
    for k, v in schema["properties"].items():
        if k not in VERBATIM_PROPERTIES:
            w(v, k)
    return out


def _annotate(schema):
    def visit(node, path, trail):
        name = path.rsplit(".", 1)[-1]
        if "$ref" in node:
            vt = value_type(name)
            node["fideon:value_type"] = vt
            title, where, printed = describe(path, node, trail)
            node["description"] = "%s (%s). %s%s" % (title, where, TYPE_TEXT[vt], printed)
            return
        title, where, printed = describe(path, node, trail)
        kind = "List of" if node.get("type") == "array" else "Section:"
        note = SCOPE_NOTES.get(path.replace("[]", ""), "")
        node["description"] = ("%s %s (%s).%s%s" % (kind, title.lower() if kind == "List of" else title,
                                                where, printed, (" " + note) if note else "")).strip()
        if node.get("type") == "object":
            for k, v in node["properties"].items():
                visit(v, "%s.%s" % (path, k) if path else k, trail + [path.rsplit(".", 1)[-1]] if path else [])
        elif node.get("type") == "array":
            it = node["items"]
            if "$ref" in it:
                node["fideon:value_type"] = value_type(name)
            else:
                for k, v in it["properties"].items():
                    visit(v, "%s[].%s" % (path, k), trail + [name])
    for k, v in schema["properties"].items():
        if k not in VERBATIM_PROPERTIES:
            visit(v, k, [])


def extend(schema):
    """Apply every extension to ``schema`` in place and return it."""
    for path, kind in ADDED:
        box = _container(schema, path)
        name = path.split(".")[-1]
        if name not in box:
            box[name] = _new(kind)
    for gone in MERGES:
        box = _container(schema, gone)
        box.pop(gone.split(".")[-1], None)
    for path, labels in ALIASES.items():
        node = _node(schema, path)
        drop = set(ALIASES_REMOVED.get(path, []))
        have = [a for a in node.get("fideon:aliases", []) if a not in labels and a not in drop]
        merged = list(labels) + have
        if merged:
            node["fideon:aliases"] = merged
        else:
            node.pop("fideon:aliases", None)
    for path, labels in ALIASES_REMOVED.items():
        if path in ALIASES:
            continue
        node = _node(schema, path)
        rest = [a for a in node.get("fideon:aliases", []) if a not in labels]
        if rest:
            node["fideon:aliases"] = rest
        else:
            node.pop("fideon:aliases", None)
    for key, node in VERBATIM_PROPERTIES.items():
        schema["properties"][key] = json.loads(json.dumps(node))
    for key, node in VERBATIM_DEFS.items():
        schema.setdefault("$defs", {})[key] = json.loads(json.dumps(node))
    _annotate(schema)
    fields = [p for p, _, k in _walk(schema) if k in ("field", "list_scalar")]
    src = schema.setdefault("fideon:source", {})
    src["field_count"] = len(fields)
    src["aliased_fields"] = json.dumps(schema).count('"fideon:aliases"')
    src["gap_analysis_extensions"] = SOURCE_NOTE
    return schema


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if the file would change")
    parser.add_argument("--schema", default=str(SCHEMA), help="schema file (default: %(default)s)")
    args = parser.parse_args(argv)
    path = Path(args.schema)
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    out = json.dumps(extend(json.loads(raw)), indent=2).replace("\n", newline) + newline
    if out == raw:
        print("%s: up to date" % path)
        return 0
    if args.check:
        print("%s: would change" % path)
        return 1
    path.write_bytes(out.encode("utf-8"))
    print("%s: extended" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
