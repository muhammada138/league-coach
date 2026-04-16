import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import Home from './Home';
import { getSummoner } from '../api/riot';
import * as router from 'react-router-dom';

// Mock the API call
vi.mock('../api/riot', () => ({
  getSummoner: vi.fn()
}));

// Mock useNavigate and useSearchHistory
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate
  };
});

const mockSaveToHistory = vi.fn();
const mockToggleSaved = vi.fn();
const mockRemoveFromHistory = vi.fn();
vi.mock('../hooks/useSearchHistory', () => ({
  default: () => ({
    saveToHistory: mockSaveToHistory,
    history: [],
    saved: [],
    toggleSaved: mockToggleSaved,
    removeFromHistory: mockRemoveFromHistory,
  })
}));

describe('Home Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage before each test
    localStorage.clear();
  });

  const renderHome = () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );
  };

  it('renders correctly with default region', () => {
    renderHome();

    // Check main headings
    expect(screen.getByText('Stop guessing.')).toBeInTheDocument();
    expect(screen.getByText('Start climbing.')).toBeInTheDocument();

    // Check input elements are present (using placeholder or roles)
    const inputs = screen.getAllByRole('textbox');
    expect(inputs.length).toBeGreaterThan(0);

    // Check default region from SearchInput (assuming it shows 'NA' or 'na1')
    expect(screen.getByText('NA')).toBeInTheDocument();
  });

  it('handles successful search and navigation', async () => {
    const mockData = { puuid: 'test-puuid', gameName: 'Faker', tagLine: 'KR1' };
    getSummoner.mockResolvedValueOnce(mockData);

    renderHome();

    // Fill in game name and tag line
    const gameNameInput = screen.getByPlaceholderText('Name');
    const tagLineInput = screen.getByPlaceholderText('TAG');

    fireEvent.change(gameNameInput, { target: { value: 'Faker' } });
    fireEvent.change(tagLineInput, { target: { value: 'KR1' } });

    // Submit form
    const submitButtons = screen.getAllByRole('button');
    const submitButton = submitButtons.find(b => b.type === 'submit') || submitButtons[submitButtons.length - 1];
    fireEvent.click(submitButton);

    // Verify API call was made
    await waitFor(() => {
      expect(getSummoner).toHaveBeenCalledWith('Faker', 'KR1', 'na1');
    });

    // Verify history was saved
    expect(mockSaveToHistory).toHaveBeenCalledWith({
      gameName: 'Faker',
      tagLine: 'KR1',
      region: 'na1'
    });

    // Verify local storage
    expect(localStorage.getItem('lastRegion')).toBe('na1');

    // Verify navigation
    expect(mockNavigate).toHaveBeenCalledWith(
      '/player/na1/Faker/KR1',
      { state: { puuid: 'test-puuid', gameCount: 20, region: 'na1' } }
    );
  });

  it('handles API errors correctly (404 Not Found)', async () => {
    const errorResponse = { response: { status: 404 } };
    getSummoner.mockRejectedValueOnce(errorResponse);

    renderHome();

    // Fill inputs
    const gameNameInput = screen.getByPlaceholderText('Name');
    const tagLineInput = screen.getByPlaceholderText('TAG');

    fireEvent.change(gameNameInput, { target: { value: 'Unknown' } });
    fireEvent.change(tagLineInput, { target: { value: '404' } });

    // Submit form
    const submitButtons = screen.getAllByRole('button');
    const submitButton = submitButtons.find(b => b.type === 'submit') || submitButtons[submitButtons.length - 1];
    fireEvent.click(submitButton);

    // Verify error message is displayed
    await waitFor(() => {
      expect(screen.getByText('Summoner not found. Check your Riot ID and tag.')).toBeInTheDocument();
    });

    // Ensure navigate was not called
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('handles general API errors correctly', async () => {
    const errorResponse = { response: { status: 500 } };
    getSummoner.mockRejectedValueOnce(errorResponse);

    renderHome();

    const gameNameInput = screen.getByPlaceholderText('Name');
    const tagLineInput = screen.getByPlaceholderText('TAG');

    fireEvent.change(gameNameInput, { target: { value: 'Error' } });
    fireEvent.change(tagLineInput, { target: { value: '500' } });

    const submitButtons = screen.getAllByRole('button');
    const submitButton = submitButtons.find(b => b.type === 'submit') || submitButtons[submitButtons.length - 1];
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Something went wrong. Try again.')).toBeInTheDocument();
    });
  });

  it('does not search if inputs are empty', async () => {
    renderHome();

    // Try submitting with empty inputs
    const submitButtons = screen.getAllByRole('button');
    const submitButton = submitButtons.find(b => b.type === 'submit') || submitButtons[submitButtons.length - 1];
    fireEvent.click(submitButton);

    // API should not be called
    expect(getSummoner).not.toHaveBeenCalled();
  });
});
