import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { LLMProvider } from '@/api/nlQuery'

interface ProviderSelectorProps {
  value: string
  onChange: (value: string) => void
  providers: LLMProvider[]
}

export function ProviderSelector({ value, onChange, providers }: ProviderSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-[200px]">
        <SelectValue placeholder="Select provider" />
      </SelectTrigger>
      <SelectContent>
        {providers.map(provider => (
          <SelectItem
            key={provider.name}
            value={provider.name}
            disabled={!provider.available}
          >
            <div className="flex items-center gap-2">
              <span>{provider.display_name}</span>
              {!provider.available && (
                <Badge variant="outline" className="text-xs">
                  Coming Soon
                </Badge>
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
