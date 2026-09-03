// The venue to print beside a symbol in the chrome: the venue its stored bars came from (as
// Market Watch read it), else the profile's default venue, else nothing.

import { useStoredVenues } from '../context/storedQuotes'
import { useSettings } from '../state/settings'
import { venueLabel } from './toolbarModel'

export function useSymbolVenue(symbol: string | null): string | null {
  const venues = useStoredVenues()
  const { profile } = useSettings()
  return (symbol && venues[symbol]) || venueLabel(profile)
}
