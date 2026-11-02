import "@nomicfoundation/hardhat-toolbox";

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.28",
    // Without the optimizer the UserStories contract goes past the 24576 bytes
    // of EIP-170 and the deploy fails, on Sepolia as well. With runs at 200 it
    // stays well under. runs says how much to optimize for repeated execution
    // rather than for size, so lowering it makes the code smaller again if that
    // is ever needed.
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
};
