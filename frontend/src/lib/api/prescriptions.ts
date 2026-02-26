/**
 * Prescription API utilities
 */

import api from '@/lib/api';

export interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing?: string;
  notes?: string;
}

export interface PrescriptionData {
  id: string;
  medicines: Medicine[];
  diagnosis?: string;
  notes?: string;
  created_at: string;
  doctor_name?: string;
  valid_until?: string;
  doctor_id?: string;
  patient_id?: string;
}

/**
 * Extract prescription data from medical record
 */
export function extractPrescriptionFromRecord(record: any): PrescriptionData | null {
  if (record.record_type !== 'prescription') {
    return null;
  }

  // First, check if prescription data is included in the record (from joined query)
  if (record.prescription) {
    return {
      id: record.id,
      medicines: record.prescription.medicines || [],
      diagnosis: record.prescription.diagnosis,
      notes: record.prescription.notes,
      created_at: record.created_at,
      doctor_name: record.doctor_name,
      valid_until: record.prescription.valid_until,
    };
  }

  // Second, try to extract from FHIR bundle
  const fhirBundle = record.fhir_bundle;
  let medicines: Medicine[] = [];

  if (fhirBundle?.entry) {
    // Extract from FHIR bundle (MedicationRequest resources)
    const medicationRequests = fhirBundle.entry.filter(
      (e: any) => e.resource?.resourceType === 'MedicationRequest'
    );

    medicines = medicationRequests.map((entry: any) => {
      const resource = entry.resource;
      const dosageInstruction = resource.dosageInstruction?.[0] || {};

      return {
        name: resource.medicationCodeableConcept?.text || 'Unknown',
        dosage: dosageInstruction.doseAndRate?.[0]?.doseQuantity?.value || '',
        frequency: dosageInstruction.timing?.code?.text || '',
        duration: '', // Not in FHIR structure
        timing: dosageInstruction.additionalInstruction?.[0]?.text,
        notes: resource.note?.[0]?.text,
      };
    });
  }

  // Fallback: Show message if no data available
  if (medicines.length === 0) {
    medicines = [{
      name: 'Prescription details not available',
      dosage: 'Please contact your doctor',
      frequency: 'N/A',
      duration: 'N/A',
      timing: undefined,
      notes: undefined,
    }];
  }

  return {
    id: record.id,
    medicines,
    diagnosis: record.title?.replace('Prescription — ', '') || undefined,
    notes: record.description,
    created_at: record.created_at,
    doctor_name: record.doctor_name,
    valid_until: undefined,
  };
}

/**
 * Fetch full prescription details by record ID
 */
export async function fetchPrescriptionDetails(recordId: string): Promise<PrescriptionData> {
  // First get the medical record
  const recordRes = await api.get(`/api/v1/patients/records/${recordId}`);
  const record = recordRes.data;

  // Try to find associated prescription entity
  try {
    const prescriptionsRes = await api.get('/api/v1/patients/prescriptions');
    const prescriptions = prescriptionsRes.data.items || [];

    // Find prescription with matching record_id
    const prescription = prescriptions.find((p: any) => p.record_id === recordId);

    if (prescription) {
      return {
        id: prescription.id,
        medicines: prescription.medicines,
        diagnosis: prescription.diagnosis,
        notes: prescription.notes,
        created_at: prescription.created_at,
        valid_until: prescription.valid_until,
        doctor_id: prescription.doctor_id,
        patient_id: prescription.patient_id,
      };
    }
  } catch (err) {
    console.warn('Could not fetch prescription details:', err);
  }

  // Fallback to extracted data from record
  return extractPrescriptionFromRecord(record) || {
    id: recordId,
    medicines: [],
    created_at: record.created_at,
  };
}
