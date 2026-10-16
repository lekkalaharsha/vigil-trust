// See unoq_secure_signer.c for status (NOT_IMPLEMENTED / HARDWARE_PENDING).
#ifndef VIGIL_UNOQ_SECURE_SIGNER_H
#define VIGIL_UNOQ_SECURE_SIGNER_H

#include "signer_interface.h"

// Initializes `signer` to the UNO Q hardware-backed signer stub. Every
// operation on the returned signer fails with a nonzero return code until
// this is actually implemented against real hardware.
void unoq_secure_signer_init(secure_signer_t *signer);

#endif  // VIGIL_UNOQ_SECURE_SIGNER_H
