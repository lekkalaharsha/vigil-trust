// SecureSigner interface -- MCU side.
//
// IMPORTANT SCOPE NOTE: in the current prototype, COSE_Sign1-style signing
// actually happens on the Linux/QRB2210 side in Python
// (edge/trust/cose_signer.py + edge/trust/identity.py), NOT on the MCU --
// matching VIGIL_TRUST_Research_and_Architecture.md section 7.1's split
// (MCU: capture/timestamp/counter/optional signing; Linux: CBOR/COSE
// envelope construction). This header defines the interface an MCU-side
// signer WOULD implement if/when signing is moved into the STM32U585's
// secure domain (the "secure signer stretch goal" in
// docs/UNO_Q_SETUP.md) -- it is declared now so the rest of the firmware
// can be written against a stable contract, but nothing in this prototype
// currently calls it.
//
// STATUS: interface only. `software_signer.cpp`'s trivial pass-through
// implementation and `unoq_secure_signer.cpp`'s stub are both
// NOT_IMPLEMENTED / HARDWARE_PENDING in the sense that neither has been
// built or exercised against a real signing operation on this board.

#ifndef VIGIL_SIGNER_INTERFACE_H
#define VIGIL_SIGNER_INTERFACE_H

#include <stdint.h>
#include <stddef.h>

#define VIGIL_SIGNATURE_LEN 64  // raw r||s, ECDSA P-256 -- matches
                                 // edge/trust/cose_signer.py's
                                 // P256_SIGNATURE_LEN
#define VIGIL_PUBLIC_KEY_DER_MAX_LEN 128

typedef struct secure_signer_vtable {
    // Signs `len` bytes at `canonical_event_bytes` (the same canonical CBOR
    // bytes edge/trust/canonical.py produces) and writes exactly
    // VIGIL_SIGNATURE_LEN bytes of raw r||s signature into `out_signature`.
    // Returns 0 on success, nonzero on failure.
    int (*sign)(void *self, const uint8_t *canonical_event_bytes, size_t len,
                uint8_t out_signature[VIGIL_SIGNATURE_LEN]);

    // Writes this signer's public key, DER-encoded SubjectPublicKeyInfo
    // (matching edge/trust/identity.py's device_id_from_public_key input
    // format), into `out_der`. Writes the actual length into
    // `out_der_len`. Returns 0 on success.
    int (*public_key_der)(void *self, uint8_t *out_der, size_t out_der_capacity, size_t *out_der_len);
} secure_signer_vtable_t;

typedef struct {
    const secure_signer_vtable_t *vtable;
    void *impl;  // implementation-specific state
} secure_signer_t;

#endif  // VIGIL_SIGNER_INTERFACE_H
