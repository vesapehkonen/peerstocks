import React, { useState } from "react";

function SearchForm({ onSearch }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      onSearch(input.trim().toUpperCase());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center justify-center gap-0 rounded overflow-hidden shadow">
      {/* Icon + Input */}
      <div className="relative w-72">
        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-lg">
          🔍
        </span>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter stock ticker (e.g. AAPL)"
          className="w-full pl-10 pr-3 py-2 border border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Button, aligned right next to input */}
      <button
        type="submit"
        className="px-4 py-2 bg-blue-500 text-white font-medium hover:bg-blue-600 transition border border-blue-500 border-l-0"
      >
        Search
      </button>
    </form>
  );
}

export default SearchForm;
