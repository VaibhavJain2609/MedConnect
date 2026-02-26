"use client"

import * as React from "react"
import { Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

export interface AutocompleteOption {
  value: string
  label: string
}

interface AutocompleteProps {
  options: AutocompleteOption[]
  value?: string
  onValueChange: (value: string) => void
  onSearchChange?: (search: string) => void
  placeholder?: string
  emptyText?: string
  allowCreate?: boolean
  onCreateNew?: (value: string) => void
  disabled?: boolean
  className?: string
}

export function Autocomplete({
  options,
  value,
  onValueChange,
  onSearchChange,
  placeholder = "Type to search...",
  emptyText = "No results found.",
  allowCreate = false,
  onCreateNew,
  disabled = false,
  className,
}: AutocompleteProps) {
  const [open, setOpen] = React.useState(false)
  const [searchValue, setSearchValue] = React.useState("")
  const [selectedLabel, setSelectedLabel] = React.useState("")
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Find selected option label
  React.useEffect(() => {
    const selected = options.find((opt) => opt.value === value)
    if (selected) {
      setSelectedLabel(selected.label)
      setSearchValue(selected.label)
    }
  }, [value, options])

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setSearchValue(newValue)
    setOpen(true)

    if (onSearchChange) {
      onSearchChange(newValue)
    }

    // Clear selection if input is cleared
    if (!newValue) {
      onValueChange("")
      setSelectedLabel("")
    }
  }

  const handleSelect = (option: AutocompleteOption) => {
    console.log('[Autocomplete] handleSelect called with:', option.label);
    onValueChange(option.value)
    setSelectedLabel(option.label)
    setSearchValue(option.label)
    setOpen(false)
  }

  const handleCreateNew = () => {
    if (onCreateNew && searchValue.trim()) {
      onCreateNew(searchValue.trim())
      setOpen(false)
    }
  }

  const handleClear = () => {
    setSearchValue("")
    setSelectedLabel("")
    onValueChange("")
    if (onSearchChange) {
      onSearchChange("")
    }
  }

  const handleInputFocus = () => {
    setOpen(true)
  }

  // Filter options based on search
  const filteredOptions = searchValue
    ? options.filter((opt) =>
        opt.label.toLowerCase().includes(searchValue.toLowerCase())
      )
    : options

  console.log('[Autocomplete] searchValue:', searchValue, 'options:', options.length, 'filtered:', filteredOptions.length);

  const showCreateButton =
    allowCreate &&
    searchValue.trim() &&
    !filteredOptions.some(
      (opt) => opt.label.toLowerCase() === searchValue.toLowerCase()
    )

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <div className="relative">
        <Input
          value={searchValue}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
          disabled={disabled}
          className="pr-8"
        />
        {searchValue && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
            onClick={handleClear}
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </Button>
        )}
      </div>

      {open && (filteredOptions.length > 0 || showCreateButton) && (
        <div className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-md max-h-[300px] overflow-auto">
          {filteredOptions.length > 0 ? (
            <div className="py-1">
              {filteredOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={cn(
                    "w-full px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center",
                    value === option.value && "bg-accent"
                  )}
                  onClick={() => handleSelect(option)}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      value === option.value ? "opacity-100" : "opacity-0"
                    )}
                  />
                  {option.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              {emptyText}
            </div>
          )}

          {showCreateButton && onCreateNew && (
            <div className="border-t p-1">
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground cursor-pointer font-medium"
                onClick={handleCreateNew}
              >
                Create "{searchValue.trim()}"
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
