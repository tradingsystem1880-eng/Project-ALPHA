import { expectTypeOf, it } from 'vitest'

import type { OwnerActionChallengeRequest, OwnerActionType } from './client'
import type { components } from './generated'

it('offers only generated owner actions with semantic ledger writes excluded', () => {
  type ServerAction = components['schemas']['OwnerActionChallengeRequest']['action_type']
  expectTypeOf<OwnerActionType>().toEqualTypeOf<Exclude<ServerAction, 'record_semantic_event'>>()
  expectTypeOf<'record_semantic_event'>().not.toMatchTypeOf<OwnerActionType>()
  expectTypeOf<OwnerActionChallengeRequest['action_type']>().toEqualTypeOf<OwnerActionType>()
})
