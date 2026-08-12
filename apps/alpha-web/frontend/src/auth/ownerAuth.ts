import {
  api,
  type OwnerActionChallengeRequest,
  type OwnerActionResult,
} from '../api/client'
import type { ResearchCase } from '../api/types'

function bytesFromBase64url(value: string): Uint8Array<ArrayBuffer> {
  const normalized = value.replaceAll('-', '+').replaceAll('_', '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  const decoded = atob(padded)
  const bytes = new Uint8Array(new ArrayBuffer(decoded.length))
  for (let index = 0; index < decoded.length; index += 1) bytes[index] = decoded.charCodeAt(index)
  return bytes
}

function base64urlFromBytes(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/u, '')
}

function descriptor(value: unknown): PublicKeyCredentialDescriptor {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('The server returned an invalid credential descriptor.')
  }
  const item = value as Record<string, unknown>
  if (typeof item.id !== 'string') throw new Error('A credential descriptor has no ID.')
  return {
    ...item,
    id: bytesFromBase64url(item.id),
  } as unknown as PublicKeyCredentialDescriptor
}

export function registrationCreationOptions(
  value: Record<string, unknown>,
): PublicKeyCredentialCreationOptions {
  if (typeof value.challenge !== 'string') throw new Error('The registration challenge is invalid.')
  if (!value.user || typeof value.user !== 'object' || Array.isArray(value.user)) {
    throw new Error('The registration user is invalid.')
  }
  const user = value.user as Record<string, unknown>
  if (typeof user.id !== 'string') throw new Error('The registration user ID is invalid.')
  return {
    ...value,
    challenge: bytesFromBase64url(value.challenge),
    user: { ...user, id: bytesFromBase64url(user.id) },
    excludeCredentials: Array.isArray(value.excludeCredentials)
      ? value.excludeCredentials.map(descriptor)
      : [],
  } as unknown as PublicKeyCredentialCreationOptions
}

export function authenticationRequestOptions(
  value: Record<string, unknown>,
): PublicKeyCredentialRequestOptions {
  if (typeof value.challenge !== 'string') throw new Error('The owner-action challenge is invalid.')
  return {
    ...value,
    challenge: bytesFromBase64url(value.challenge),
    allowCredentials: Array.isArray(value.allowCredentials)
      ? value.allowCredentials.map(descriptor)
      : [],
  } as PublicKeyCredentialRequestOptions
}

function credentialBase(credential: PublicKeyCredential): Record<string, unknown> {
  return {
    id: credential.id,
    type: credential.type,
    rawId: base64urlFromBytes(credential.rawId),
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
  }
}

export function serializeRegistrationCredential(
  credential: PublicKeyCredential,
): Record<string, unknown> {
  const response = credential.response
  if (!(response instanceof AuthenticatorAttestationResponse)) {
    throw new Error('Touch ID returned an unexpected registration response.')
  }
  return {
    ...credentialBase(credential),
    response: {
      clientDataJSON: base64urlFromBytes(response.clientDataJSON),
      attestationObject: base64urlFromBytes(response.attestationObject),
      transports: response.getTransports(),
    },
  }
}

export function serializeAuthenticationCredential(
  credential: PublicKeyCredential,
): Record<string, unknown> {
  const response = credential.response
  if (!(response instanceof AuthenticatorAssertionResponse)) {
    throw new Error('Touch ID returned an unexpected owner-action response.')
  }
  return {
    ...credentialBase(credential),
    response: {
      authenticatorData: base64urlFromBytes(response.authenticatorData),
      clientDataJSON: base64urlFromBytes(response.clientDataJSON),
      signature: base64urlFromBytes(response.signature),
      userHandle: response.userHandle === null ? null : base64urlFromBytes(response.userHandle),
    },
  }
}

function requireWebAuthn(): CredentialsContainer {
  if (!window.isSecureContext || !window.PublicKeyCredential || !navigator.credentials) {
    throw new Error('Touch ID requires the canonical http://localhost:8801 Workstation origin.')
  }
  return navigator.credentials
}

export async function registerOwnerCredential(token: string): Promise<Record<string, unknown>> {
  const credentials = requireWebAuthn()
  const envelope = await api.ownerRegistrationOptions(token)
  const created = await credentials.create({
    publicKey: registrationCreationOptions(envelope.public_key),
  })
  if (!(created instanceof PublicKeyCredential)) throw new Error('Touch ID registration was cancelled.')
  return api.ownerRegistrationFinish(
    token,
    envelope.challenge_id,
    serializeRegistrationCredential(created),
  )
}

export async function performOwnerAction(
  request: OwnerActionChallengeRequest,
): Promise<OwnerActionResult> {
  const credentials = requireWebAuthn()
  const envelope = await api.ownerActionChallenge(request)
  const asserted = await credentials.get({
    publicKey: authenticationRequestOptions(envelope.public_key),
  })
  if (!(asserted instanceof PublicKeyCredential)) throw new Error('Touch ID verification was cancelled.')
  return api.ownerActionPerform(
    envelope.challenge_id,
    serializeAuthenticationCredential(asserted),
    request.payload,
  )
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value !== null && typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(',')}}`
  }
  return JSON.stringify(value)
}

export async function researchCaseRevision(researchCase: ResearchCase): Promise<string> {
  const payload = {
    schema: 'ResearchCaseRevisionV1',
    project_id: researchCase.project_id,
    active_contract_id: researchCase.active_contract_id,
    phase: researchCase.phase,
    execution_state: researchCase.execution_state,
    source_pack_id: researchCase.source_pack_id,
  }
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(payload)))
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function contentAddressHash(identifier: string): string {
  const separator = identifier.indexOf('_')
  const digest = separator === -1 ? '' : identifier.slice(separator + 1)
  if (!/^[0-9a-f]{64}$/u.test(digest)) throw new Error('The active artifact is not content-addressed.')
  return digest
}
