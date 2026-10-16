// UnoQSecureSigner -- target hardware-backed implementation of
// secure_signer_t using the STM32U585's TrustZone secure domain / PKA /
// HUK-derived key storage
// (https://www.st.com/en/microcontrollers-microprocessors/stm32u585ai.html).
//
// STATUS: NOT_IMPLEMENTED. Every function below returns an explicit
// failure code rather than a fake signature, per
// CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 6 ("no fake test results") and
// the hackathon CLAUDE.md section 24.6 (experimental features must not
// silently feed confirmed evidence). Implementing this for real requires:
//   1. Confirming which secure-domain APIs are actually reachable from
//      Zephyr's Arduino Core on this specific board (not assumed here).
//   2. A secure provisioning step to derive/store the P-256 private key
//      inside the secure domain so it never appears in normal-world
//      memory.
//   3. A secure-to-normal-world call gate (e.g. a Zephyr secure service)
//      that accepts a hash/digest and returns only the signature, never
//      the key.
// None of that has been attempted here without real hardware to validate
// against -- see docs/UNO_Q_SETUP.md.

#include "signer_interface.h"
#include "unoq_secure_signer.h"

static int unoq_secure_signer_sign(void *self, const uint8_t *canonical_event_bytes, size_t len,
                                    uint8_t out_signature[VIGIL_SIGNATURE_LEN]) {
    (void)self;
    (void)canonical_event_bytes;
    (void)len;
    (void)out_signature;
    return -1;  // HARDWARE_PENDING: not implemented
}

static int unoq_secure_signer_public_key_der(void *self, uint8_t *out_der, size_t out_der_capacity,
                                              size_t *out_der_len) {
    (void)self;
    (void)out_der;
    (void)out_der_capacity;
    (void)out_der_len;
    return -1;  // HARDWARE_PENDING: not implemented
}

static const secure_signer_vtable_t UNOQ_SECURE_SIGNER_VTABLE = {
    .sign = unoq_secure_signer_sign,
    .public_key_der = unoq_secure_signer_public_key_der,
};

void unoq_secure_signer_init(secure_signer_t *signer) {
    signer->vtable = &UNOQ_SECURE_SIGNER_VTABLE;
    signer->impl = 0;
}
