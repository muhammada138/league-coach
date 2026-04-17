import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SearchInput from './SearchInput';

// Mock the RegionSelector component
vi.mock('./RegionSelector', () => ({
  default: ({ value, onChange }) => (
    <select data-testid="region-selector" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="na1">NA1</option>
      <option value="euw1">EUW1</option>
    </select>
  )
}));

// Mock the useSearchHistory hook
vi.mock('../hooks/useSearchHistory', () => ({
  default: () => ({
    history: [],
    saved: [],
    toggleSaved: vi.fn(),
    removeFromHistory: vi.fn()
  })
}));

describe('SearchInput', () => {
  const defaultProps = {
    region: 'na1',
    setRegion: vi.fn(),
    gameName: '',
    setGameName: vi.fn(),
    tagLine: '',
    setTagLine: vi.fn(),
    onSubmit: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<SearchInput {...defaultProps} />);

    // Check if the inputs are rendered
    expect(screen.getByPlaceholderText('Name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('TAG')).toBeInTheDocument();
    expect(screen.getByTestId('region-selector')).toBeInTheDocument();
  });

  it('calls onSubmit when form is submitted', () => {
    render(<SearchInput {...defaultProps} />);

    const form = screen.getByRole('button').closest('form');
    fireEvent.submit(form);

    expect(defaultProps.onSubmit).toHaveBeenCalled();
  });

  it('splits gameName and tagLine when # is typed or pasted in gameName input', () => {
    render(<SearchInput {...defaultProps} />);

    const gameNameInput = screen.getByPlaceholderText('Name');

    // Simulate user typing a string with a '#'
    fireEvent.change(gameNameInput, { target: { value: 'Faker#T1' } });

    // It should call setGameName with the part before '#'
    expect(defaultProps.setGameName).toHaveBeenCalledWith('Faker');

    // It should call setTagLine with the part after '#'
    expect(defaultProps.setTagLine).toHaveBeenCalledWith('T1');
  });

  it('handles multiple # correctly', () => {
    render(<SearchInput {...defaultProps} />);

    const gameNameInput = screen.getByPlaceholderText('Name');

    // Simulate user typing a string with multiple '#'
    fireEvent.change(gameNameInput, { target: { value: 'Name#TAG#EXTRA' } });

    // It should call setGameName with the part before the first '#'
    expect(defaultProps.setGameName).toHaveBeenCalledWith('Name');

    // It should call setTagLine with the rest joined by '#'
    expect(defaultProps.setTagLine).toHaveBeenCalledWith('TAG#EXTRA');
  });
});
