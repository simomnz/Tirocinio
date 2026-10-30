import "@nomicfoundation/hardhat-toolbox";

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.28",
    // Senza optimizer il contratto UserStories supera i 24576 byte di EIP-170
    // e il deploy fallisce, anche su Sepolia. Con runs 200 resta largamente
    // sotto. runs dice quanto ottimizzare per l'uso ripetuto invece che per la
    // dimensione: abbassarlo rimpicciolisce ancora, se un giorno servisse.
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
};
