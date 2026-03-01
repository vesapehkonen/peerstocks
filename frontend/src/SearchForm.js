import React, { useState } from "react";

function SearchForm({ onSearch }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    const value = input.trim().toUpperCase();
    if (value) onSearch(value);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full flex justify-center">
      <div
        className="flex w-full max-w-sm items-stretch
                   rounded-lg overflow-hidden
                   border border-gray-200 dark:border-gray-700
                   bg-white dark:bg-gray-800"
      >
        {/* Icon */}
        <div className="flex items-center px-3 text-gray-400">🔍</div>

        {/* Input */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter stock ticker (e.g. AAPL)"
          className="flex-1 px-3 py-2 outline-none bg-transparent
                     text-gray-900 dark:text-gray-100
                     placeholder:text-gray-400 dark:placeholder:text-gray-500"
        />

        {/* Button */}
        <button
          type="submit"
          className="px-5 py-2 font-medium text-white
                     bg-blue-600 hover:bg-blue-700 transition"
        >
          Search
        </button>
      </div>
    </form>
  );
}

export default SearchForm;
